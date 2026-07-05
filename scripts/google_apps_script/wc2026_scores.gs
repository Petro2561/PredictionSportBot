/**
 * ЧМ-2026: счёт с championat.com → лист «Стадия 1»
 *
 * 1. Вставить в Apps Script
 * 2. installTrigger() — раз
 * 3. updateWorldCupScores() — проверка
 * 4. debugChampionatParse() — отладка
 *
 * Раскладка листа (как в боте):
 *   Строка 2 — заголовки «Тур 1», «Тур 2», … в начале блоков (B, I, P, …).
 *   Под каждым заголовком — матчи тура в одной колонке; слева от названия —
 *   дата матча (B→A, I→H, P→O …), а счёт в двух колонках справа (B→C/D …).
 *   Между 1-й и 2-й половиной матчей — одна пустая строка. Скрипт сам находит
 *   блоки и границу расписания (две пустые строки подряд = конец расписания,
 *   дальше идут «ОБЩИЙ ЗАЧЁТ» / «N ТУР»).
 */

const CONFIG = {
  SHEET_NAME: 'Стадия 1',
  SCHEDULE_HEADER_ROW: 2,
  FIRST_MATCH_ROW: 3,
  MAX_SCAN_ROWS: 40, // предохранитель на число строк расписания
  STOP_AFTER_BLANK_ROWS: 2, // столько пустых строк подряд = конец расписания
  MAX_BLOCK_COLS: 60, // докуда искать заголовки «Тур N» в строке 2
  CALENDAR_URL: 'https://www.championat.com/football/_worldcup/tournament/6858/calendar/',
  // Туры, которые скрипт НЕ трогает (счёт/даты не перезаписывает). Групповой этап
  // завершён, поэтому 1–3 заморожены; активным остаётся плей-офф (Тур 4 = 1/16 финала).
  FROZEN_TOURS: [1, 2, 3],
};

/**
 * Алиасы названий. Ключи и значения — в КАНОНИЧЕСКОМ виде
 * (нижний регистр, ё→е, без апострофов/дефисов/пробелов), как их делает
 * normalizeTeam_. Например «Кот-д'Ивуар» → «котдивуар», «Кабо-Верде» → «кабоверде»
 * совпадают сами по себе независимо от вида апострофа/дефиса.
 */
const TEAM_ALIASES = {
  'южнаяафрика': 'юар',
  'корея': 'южнаякорея',
  'соединенныештаты': 'сша',
  'голландия': 'нидерланды',
  'конгодр': 'дрконго',
};

/**
 * Зафиксированные счета. Ключ — пара команд в каноническом виде (normalizeTeam_),
 * порядок как на листе: «Бельгия – Сенегал» → «бельгия|сенегал».
 * Championat иногда отдаёт неверный результат — здесь задаётся правильный счёт,
 * который скрипт пишет вместо данных с сайта.
 */
const PINNED_SCORES = {
  'бельгия|сенегал': { home: 2, away: 2 },
  'аргентина|кабоверде': { home: 1, away: 1 },
};

function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'updateWorldCupScores') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger('updateWorldCupScores')
    .timeBased()
    .everyMinutes(5)
    .create();
  Logger.log('Триггер каждые 5 минут установлен.');
}

function uninstallTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'updateWorldCupScores') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function updateWorldCupScores() {
  Logger.log('=== updateWorldCupScores START ===');

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) {
    throw new Error('Лист «' + CONFIG.SHEET_NAME + '» не найден');
  }

  const html = fetchCalendarHtml_();
  const parseResult = parseChampionatCalendar_(html);
  const scoreMap = parseResult.map;

  Logger.log('Championat: строк матчей=' + parseResult.totalRows +
    ', со счётом=' + parseResult.withScore +
    ', без счёта=' + parseResult.withoutScore);

  const blocks = findTourBlocks_(sheet);
  if (!blocks.length) {
    throw new Error('Не найдены заголовки «Тур N» в строке ' + CONFIG.SCHEDULE_HEADER_ROW);
  }
  Logger.log('Найдено блоков туров: ' + blocks.length +
    ' (' + blocks.map(function (b) { return b.title; }).join(', ') + ')');

  let updatedScores = 0;
  let updatedDates = 0;
  let notFound = 0;
  let frozenSkipped = 0;
  let pinnedScores = 0;

  const logFn = function (msg) {
    Logger.log(msg);
    if (msg.indexOf('НЕ НАЙДЕНО') >= 0) notFound++;
  };

  const frozenTours = CONFIG.FROZEN_TOURS || [];

  // граница расписания: STOP_AFTER_BLANK_ROWS пустых строк подряд в колонке тура.
  // Промежуток между половинами — 1 пустая строка, поэтому не обрывает цикл.
  blocks.forEach(function (block) {
    // замороженные туры (завершённый групповой этап) не трогаем вообще:
    // ни счёт, ни даты — оставляем как есть, чтобы их нельзя было затереть.
    if (block.number != null && frozenTours.indexOf(block.number) >= 0) {
      frozenSkipped++;
      Logger.log('Тур ' + block.number + ' заморожен (FROZEN_TOURS) — пропускаю.');
      return;
    }
    let blankRun = 0;
    for (let i = 0; i < CONFIG.MAX_SCAN_ROWS; i++) {
      const row = CONFIG.FIRST_MATCH_ROW + i;
      const label = String(sheet.getRange(row, block.labelCol).getValue() || '').trim();
      if (!label) {
        blankRun++;
        if (blankRun >= CONFIG.STOP_AFTER_BLANK_ROWS) break;
        continue;
      }
      blankRun = 0;
      const res = updateRow_(
        sheet, row, block.labelCol, block.dateCol, block.score1Col, block.score2Col,
        scoreMap, logFn
      );
      updatedScores += res.score;
      updatedDates += res.date;
      pinnedScores += res.pinned;
    }
  });

  const summary =
    'Обновлено счётов: ' + updatedScores + '\n' +
    'Обновлено дат: ' + updatedDates + '\n' +
    'Закреплённых счётов: ' + pinnedScores + '\n' +
    'Туров на листе: ' + blocks.length + '\n' +
    'Заморожено туров: ' + frozenSkipped + ' (' + frozenTours.join(', ') + ')\n' +
    'Championat матчей: ' + parseResult.totalRows + '\n' +
    'Со счётом: ' + parseResult.withScore + '\n' +
    'В scoreMap: ' + Object.keys(scoreMap).length + '\n' +
    'Не найдено: ' + notFound;

  sheet.getRange('A1').setNote(
    Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd.MM.yyyy HH:mm:ss') +
    '\n' + summary
  );

  Logger.log('--- Итог ---');
  Logger.log(summary);
  Logger.log('=== END ===');
}

/** Находит блоки туров по заголовкам «Тур N» в строке расписания. */
function findTourBlocks_(sheet) {
  const header = sheet
    .getRange(CONFIG.SCHEDULE_HEADER_ROW, 1, 1, CONFIG.MAX_BLOCK_COLS)
    .getValues()[0];
  const blocks = [];
  for (let i = 0; i < header.length; i++) {
    const text = String(header[i] || '').trim();
    // важно: \b в JS не работает с кириллицей, поэтому проверяем префикс
    if (text.toLowerCase().indexOf('тур') === 0) {
      const labelCol = i + 1; // 1-based
      const numMatch = text.match(/(\d+)/);
      blocks.push({
        labelCol: labelCol,
        dateCol: labelCol - 1, // дата слева от названий (B→A, I→H, P→O …)
        score1Col: labelCol + 1,
        score2Col: labelCol + 2,
        title: text,
        number: numMatch ? parseInt(numMatch[1], 10) : null,
      });
    }
  }
  return blocks;
}

function debugChampionatParse() {
  const html = fetchCalendarHtml_();
  Logger.log('HTML length: ' + html.length);

  const result = parseChampionatCalendar_(html);
  Logger.log('Всего строк: ' + result.totalRows);
  Logger.log('Со счётом: ' + result.withScore);
  Logger.log('Без счёта: ' + result.withoutScore);

  result.matches.forEach(function (m, i) {
    Logger.log(
      (i + 1) + '. ' + m.home + ' — ' + m.away +
      ' | ' + (m.scoreText || 'нет счёта') +
      ' | ' + (m.dateText || 'нет даты') +
      ' | played=' + m.played +
      ' | tour=' + m.tour + ' | ' + m.group
    );
  });

  Logger.log('--- scoreMap keys ---');
  Object.keys(result.map).forEach(function (k) {
    const v = result.map[k];
    Logger.log(k + ' → ' + v.home + ':' + v.away + ' | ' + (v.date || '—'));
  });
}

function fetchCalendarHtml_() {
  const response = UrlFetchApp.fetch(CONFIG.CALENDAR_URL, {
    muteHttpExceptions: true,
    followRedirects: true,
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; PredictionSportBot/1.0)',
      'Accept-Language': 'ru-RU,ru;q=0.9',
    },
  });
  const code = response.getResponseCode();
  if (code !== 200) {
    throw new Error('Championat HTTP ' + code);
  }
  return response.getContentText('UTF-8');
}

function parseChampionatCalendar_(html) {
  const map = {};
  const matches = [];
  let totalRows = 0;
  let withScore = 0;
  let withoutScore = 0;

  const rowRe = /<tr\b[^>]*class="[^"]*stat-results__row[^"]*"[^>]*>([\s\S]*?)<\/tr>/gi;
  let rowMatch;

  while ((rowMatch = rowRe.exec(html)) !== null) {
    const rowHtml = rowMatch[0];
    const rowBody = rowMatch[1];
    totalRows++;

    const playedMatch = rowHtml.match(/data-played="(\d+)"/);
    const played = playedMatch ? playedMatch[1] === '1' : false;

    const groupMatch = rowBody.match(/stat-results__group[^>]*>([^<]+)</);
    const tourMatch = rowBody.match(/stat-results__tour-num[^>]*>([^<]+)</);
    const group = groupMatch ? groupMatch[1].trim() : '';
    const tour = tourMatch ? tourMatch[1].trim() : '';

    const names = [];
    const nameRe = /<span class="table-item__name">([^<]+)<\/span>/gi;
    let nameMatch;
    while ((nameMatch = nameRe.exec(rowBody)) !== null) {
      names.push(nameMatch[1].trim());
    }
    if (names.length < 2) continue;

    const home = normalizeTeam_(names[0]);
    const away = normalizeTeam_(names[1]);

    const scoreMatch = rowBody.match(/stat-results__count-main">\s*([^<]+?)\s*<\/span>/);
    const scoreText = scoreMatch ? scoreMatch[1].trim() : '';
    const parsedScore = parseScoreText_(scoreText);

    const dateText = parseDateText_(rowBody);

    const item = {
      home: names[0],
      away: names[1],
      homeKey: home,
      awayKey: away,
      scoreText: scoreText,
      dateText: dateText,
      played: played,
      group: group,
      tour: tour,
    };
    matches.push(item);

    // дату пишем для всех матчей (даже будущих, без счёта)
    map[pairKey_(home, away)] = {
      home: parsedScore ? parsedScore.home : null,
      away: parsedScore ? parsedScore.away : null,
      date: dateText,
      played: played,
      source: 'championat',
    };

    if (parsedScore) {
      withScore++;
    } else {
      withoutScore++;
    }
  }

  return { map: map, matches: matches, totalRows: totalRows, withScore: withScore, withoutScore: withoutScore };
}

/** Дата + время матча («11.06.2026 22:00»), либо только дата, либо ''. */
function parseDateText_(rowBody) {
  const dateMatch = rowBody.match(/(\d{2}\.\d{2}\.\d{4})/);
  if (!dateMatch) return '';
  // время в отдельном теге, поэтому ищем HH:MM отдельно (счёт «2 : 0» не подходит)
  const timeMatch = rowBody.match(/([01]\d|2[0-3]):([0-5]\d)/);
  return timeMatch ? dateMatch[1] + ' ' + timeMatch[0] : dateMatch[1];
}

function parseScoreText_(text) {
  if (!text) return null;
  const cleaned = text.replace(/\u2013|\u2014|–|—/g, '-').trim();
  if (/^[-–—\s:]+$/.test(cleaned)) return null;

  const m = cleaned.match(/(\d+)\s*:\s*(\d+)/);
  if (!m) return null;
  return { home: parseInt(m[1], 10), away: parseInt(m[2], 10) };
}

function updateRow_(sheet, row, labelCol, dateCol, score1Col, score2Col, scoreMap, logFn) {
  const cellRef = columnLetter_(labelCol) + row;
  const result = { score: 0, date: 0, pinned: 0 };

  const label = String(sheet.getRange(row, labelCol).getValue() || '').trim();
  if (!label) return result; // пустая строка (в т.ч. промежуток между половинами)

  const teams = parseMatchLabel_(label);
  if (!teams) {
    if (logFn) logFn(cellRef + ': не распарсилось → «' + label + '»');
    return result;
  }

  const pinned = lookupPinnedScore_(teams[0], teams[1]);
  if (pinned) {
    const found = lookupMatch_(scoreMap, teams[0], teams[1]);
    if (found && found.date && dateCol >= 1) {
      sheet.getRange(row, dateCol).setValue(found.date);
      result.date = 1;
    }
    sheet.getRange(row, score1Col).setValue(pinned.home);
    sheet.getRange(row, score2Col).setValue(pinned.away);
    result.score = 1;
    result.pinned = 1;
    if (logFn) {
      logFn(cellRef + ': «' + label + '» → закреплено ' + pinned.home + ':' + pinned.away +
        ' (Championat игнорируется)');
    }
    return result;
  }

  const found = lookupMatch_(scoreMap, teams[0], teams[1]);
  if (!found) {
    if (logFn) logFn(cellRef + ': «' + label + '» → НЕ НАЙДЕНО [' + teams[0] + '|' + teams[1] + ']');
    return result;
  }

  if (found.date && dateCol >= 1) {
    sheet.getRange(row, dateCol).setValue(found.date);
    result.date = 1;
  }

  if (found.home != null && found.away != null) {
    sheet.getRange(row, score1Col).setValue(found.home);
    sheet.getRange(row, score2Col).setValue(found.away);
    result.score = 1;
    if (logFn) logFn(cellRef + ': «' + label + '» → ' + found.home + ':' + found.away +
      (found.date ? ' (' + found.date + ')' : ''));
  } else if (logFn) {
    logFn(cellRef + ': «' + label + '» → дата ' + (found.date || '—') + ', счёта нет');
  }

  return result;
}

function parseMatchLabel_(label) {
  // разделитель команд — тире С ПРОБЕЛАМИ вокруг; внутренние дефисы
  // в названиях («Кот-д'Ивуар», «Кабо-Верде») не трогаем
  const parts = label.split(/\s+[–—-]\s+/);
  if (parts.length !== 2) return null;
  return [normalizeTeam_(parts[0]), normalizeTeam_(parts[1])];
}

function lookupMatch_(scoreMap, home, away) {
  const direct = scoreMap[pairKey_(home, away)];
  if (direct) return { home: direct.home, away: direct.away, date: direct.date };
  const reverse = scoreMap[pairKey_(away, home)];
  if (reverse) return { home: reverse.away, away: reverse.home, date: reverse.date };
  return null;
}

function lookupPinnedScore_(home, away) {
  const direct = PINNED_SCORES[pairKey_(home, away)];
  if (direct) return { home: direct.home, away: direct.away };
  const reverse = PINNED_SCORES[pairKey_(away, home)];
  if (reverse) return { home: reverse.away, away: reverse.home };
  return null;
}

function pairKey_(a, b) {
  return a + '|' + b;
}

function columnLetter_(index) {
  let letters = '';
  while (index > 0) {
    const remainder = (index - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    index = Math.floor((index - 1) / 26);
  }
  return letters;
}

function normalizeTeam_(name) {
  let n = String(name || '')
    .trim()
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[’ʼ`´'‘]/g, '') // апострофы любого вида
    .replace(/[–—−-]/g, '')    // дефисы/тире любого вида
    .replace(/\s+/g, '');      // пробелы
  if (TEAM_ALIASES[n]) return TEAM_ALIASES[n];
  return n;
}
