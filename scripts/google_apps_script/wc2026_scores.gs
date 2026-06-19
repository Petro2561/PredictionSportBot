/**
 * ЧМ-2026: автоматическое обновление счёта на листе «Стадия 1».
 *
 * Установка:
 * 1. Google Таблица → Расширения → Apps Script → вставить этот файл.
 * 2. Зарегистрироваться на https://www.football-data.org/client/register (бесплатно).
 * 3. Запустить один раз setApiToken('ВАШ_ТОКЕН') или задать FOOTBALL_DATA_TOKEN ниже.
 * 4. Запустить один раз installTrigger() — обновление каждые 5 минут.
 * 5. Для проверки: updateWorldCupScores()
 *
 * Раскладка листа (как в боте):
 *   Строка 2 — заголовки «Тур 1», «Тур 2», … в начале блоков (B, I, P, …).
 *   Под каждым заголовком — матчи тура в одной колонке, счёт в двух соседних
 *   колонках (B→C/D, I→J/K, P→Q/R и т.д.). Между 1-й и 2-й половиной матчей —
 *   одна пустая строка. Скрипт сам находит блоки и границу расписания
 *   (останавливается, когда в колонке A появляется «ОБЩИЙ ЗАЧЁТ» / «N ТУР»).
 */

const CONFIG = {
  SHEET_NAME: 'Стадия 1',
  SCHEDULE_HEADER_ROW: 2,
  FIRST_MATCH_ROW: 3,
  MAX_SCAN_ROWS: 40, // предохранитель на случай, если колонка A пустая
  MAX_BLOCK_COLS: 60, // докуда искать заголовки «Тур N» в строке 2
  // Оставьте пустым, если токен задан через setApiToken()
  FOOTBALL_DATA_TOKEN: '',
  API_URL: 'https://api.football-data.org/v4/competitions/WC/matches?season=2026',
};

/** Русские / альтернативные названия → как в football-data.org */
const TEAM_ALIASES = {
  'мексика': 'mexico',
  'юар': 'south africa',
  'южная корея': 'korea republic',
  'корея': 'korea republic',
  'чехия': 'czechia',
  'канада': 'canada',
  'босния и герцеговина': 'bosnia-herzegovina',
  'сша': 'united states',
  'парагвай': 'paraguay',
  'катар': 'qatar',
  'швейцария': 'switzerland',
  'бразилия': 'brazil',
  'марокко': 'morocco',
  'гаити': 'haiti',
  'шотландия': 'scotland',
  'австралия': 'australia',
  'турция': 'turkey',
  'германия': 'germany',
  'кюрасао': 'curacao',
  'нидерланды': 'netherlands',
  'голландия': 'netherlands',
  'япония': 'japan',
  "кот-д'ивуар": 'ivory coast',
  'кот дивуар': 'ivory coast',
  'эквадор': 'ecuador',
  'швеция': 'sweden',
  'тунис': 'tunisia',
  'испания': 'spain',
  'кабо-верде': 'cape verde',
  'бельгия': 'belgium',
  'египет': 'egypt',
  'саудовская аравия': 'saudi arabia',
  'уругвай': 'uruguay',
  'иран': 'iran',
  'новая зеландия': 'new zealand',
  'франция': 'france',
  'сенегал': 'senegal',
  'ирак': 'iraq',
  'норвегия': 'norway',
  'аргентина': 'argentina',
  'алжир': 'algeria',
  'австрия': 'austria',
  'иордания': 'jordan',
  'португалия': 'portugal',
  'др конго': 'congo dr',
  'конго др': 'congo dr',
  'англия': 'england',
  'хорватия': 'croatia',
  'гана': 'ghana',
  'панама': 'panama',
  'узбекистан': 'uzbekistan',
  'колумбия': 'colombia',
  // английские варианты из старой БД
  'korea republic': 'korea republic',
  'czechia': 'czechia',
  'czech republic': 'czechia',
  'united states': 'united states',
  'usa': 'united states',
  'bosnia and herzegovina': 'bosnia-herzegovina',
  "côte d'ivoire": 'ivory coast',
  'cote divoire': 'ivory coast',
  'curaçao': 'curacao',
  'curacao': 'curacao',
  'cabo verde': 'cape verde',
  'cape verde': 'cape verde',
  'congo dr': 'congo dr',
  'dr congo': 'congo dr',
};

function setApiToken(token) {
  PropertiesService.getScriptProperties().setProperty('FOOTBALL_DATA_TOKEN', token);
  Logger.log('Токен сохранён в свойствах скрипта.');
}

function getApiToken_() {
  const fromProps = PropertiesService.getScriptProperties().getProperty('FOOTBALL_DATA_TOKEN');
  return (CONFIG.FOOTBALL_DATA_TOKEN || fromProps || '').trim();
}

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
  Logger.log('Триггер: updateWorldCupScores каждые 5 минут.');
}

function uninstallTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'updateWorldCupScores') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  Logger.log('Триггер удалён.');
}

function updateWorldCupScores() {
  const token = getApiToken_();
  if (!token) {
    throw new Error('Задайте токен: setApiToken("...") или CONFIG.FOOTBALL_DATA_TOKEN');
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) {
    throw new Error('Лист «' + CONFIG.SHEET_NAME + '» не найден');
  }

  const apiMatches = fetchApiMatches_(token);
  const scoreMap = buildScoreMap_(apiMatches);

  const blocks = findTourBlocks_(sheet);
  if (!blocks.length) {
    throw new Error('Не найдены заголовки «Тур N» в строке ' + CONFIG.SCHEDULE_HEADER_ROW);
  }

  let updated = 0;
  blocks.forEach(function (block) {
    const lastRow = CONFIG.FIRST_MATCH_ROW + CONFIG.MAX_SCAN_ROWS;
    for (let row = CONFIG.FIRST_MATCH_ROW; row <= lastRow; row++) {
      // граница расписания: ниже начинаются «ОБЩИЙ ЗАЧЁТ» / «N ТУР» (колонка A)
      const aCell = String(sheet.getRange(row, 1).getValue() || '').trim();
      if (aCell) break;
      updated += updateRow_(
        sheet, row, block.labelCol, block.score1Col, block.score2Col, scoreMap
      );
    }
  });

  sheet.getRange('A1').setNote(
    'Счёт обновлён: ' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd.MM.yyyy HH:mm:ss') +
    ' (матчей: ' + updated + ')'
  );
  Logger.log('Обновлено ячеек счёта: ' + updated + ' (туров: ' + blocks.length + ')');
}

/** Находит блоки туров по заголовкам «Тур N» в строке расписания. */
function findTourBlocks_(sheet) {
  const headerValues = sheet
    .getRange(CONFIG.SCHEDULE_HEADER_ROW, 1, 1, CONFIG.MAX_BLOCK_COLS)
    .getValues()[0];
  const blocks = [];
  headerValues.forEach(function (value, index) {
    if (/^\s*Тур\b/i.test(String(value || ''))) {
      const labelCol = index + 1; // 1-based
      blocks.push({
        labelCol: labelCol,
        score1Col: labelCol + 1,
        score2Col: labelCol + 2,
      });
    }
  });
  return blocks;
}

function fetchApiMatches_(token) {
  const response = UrlFetchApp.fetch(CONFIG.API_URL, {
    muteHttpExceptions: true,
    headers: { 'X-Auth-Token': token },
  });
  const code = response.getResponseCode();
  const body = response.getContentText();
  if (code !== 200) {
    throw new Error('football-data.org HTTP ' + code + ': ' + body.substring(0, 300));
  }
  const data = JSON.parse(body);
  return data.matches || [];
}

function buildScoreMap_(apiMatches) {
  const map = {};
  apiMatches.forEach(function (match) {
    if (!match.score || match.score.fullTime == null) return;
    if (match.status !== 'FINISHED' && match.status !== 'IN_PLAY' && match.status !== 'PAUSED') {
      return;
    }
    const home = normalizeTeam_(match.homeTeam.name);
    const away = normalizeTeam_(match.awayTeam.name);
    const h = match.score.fullTime.home;
    const a = match.score.fullTime.away;
    if (h == null || a == null) return;
    map[pairKey_(home, away)] = { home: h, away: a, sheetHome: home, sheetAway: away };
  });
  return map;
}

function updateRow_(sheet, row, labelCol, score1Col, score2Col, scoreMap) {
  const label = String(sheet.getRange(row, labelCol).getValue() || '').trim();
  if (!label) return 0;

  const teams = parseMatchLabel_(label);
  if (!teams) return 0;

  const found = lookupScore_(scoreMap, teams[0], teams[1]);
  if (!found) return 0;

  sheet.getRange(row, score1Col).setValue(found.home);
  sheet.getRange(row, score2Col).setValue(found.away);
  return 1;
}

function parseMatchLabel_(label) {
  const parts = label.split(/\s*[–\-]\s*/);
  if (parts.length !== 2) return null;
  return [normalizeTeam_(parts[0]), normalizeTeam_(parts[1])];
}

function lookupScore_(scoreMap, home, away) {
  const direct = scoreMap[pairKey_(home, away)];
  if (direct) {
    return { home: direct.home, away: direct.away };
  }
  const reverse = scoreMap[pairKey_(away, home)];
  if (reverse) {
    return { home: reverse.away, away: reverse.home };
  }
  return null;
}

function pairKey_(a, b) {
  return a + '|' + b;
}

function normalizeTeam_(name) {
  let n = String(name || '')
    .trim()
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/\s+/g, ' ');
  n = n.replace(/[çãáàâäéèêëíìîïóòôöúùûüñ]/g, function (c) {
    const map = { ç: 'c', ã: 'a', á: 'a', à: 'a', â: 'a', ä: 'a', é: 'e', è: 'e', ê: 'e', ë: 'e',
      í: 'i', ì: 'i', î: 'i', ï: 'i', ó: 'o', ò: 'o', ô: 'o', ö: 'o', ú: 'u', ù: 'u', û: 'u', ü: 'u', ñ: 'n' };
    return map[c] || c;
  });
  if (TEAM_ALIASES[n]) return TEAM_ALIASES[n];
  return n;
}
