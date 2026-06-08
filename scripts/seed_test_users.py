"""Добавляет 20 тестовых пользователей в существующий турнир."""

import sqlite3
from pathlib import Path

TOURNAMENT_ID = 1

TEST_USERS = [
    (900_000_001, "Алексей Голиков", "golikov_alex"),
    (900_000_002, "Мария Ставочник", "maria_bets"),
    (900_000_003, "Дмитрий Оффсайд", "dimka_offside"),
    (900_000_004, "Елена Пенальти", "lena_penalti"),
    (900_000_005, "Игорь Вингер", "igor_winger"),
    (900_000_006, "Наталья Трибуна", "natasha_tribuna"),
    (900_000_007, "Сергей Дриблинг", "serg_dribling"),
    (900_000_008, "Ольга Кипер", "olga_keeper"),
    (900_000_009, "Павел Хет-трик", "pavel_hattrick"),
    (900_000_010, "Анна Скамейка", "anna_bench"),
    (900_000_011, "Виктор Тактик", "viktor_tactic"),
    (900_000_012, "Юлия Фланг", "yulia_flank"),
    (900_000_013, "Роман Аут", "roman_out"),
    (900_000_014, "Ксения Дрибл", "ksenia_dribl"),
    (900_000_015, "Артём Сейв", "artem_save"),
    (900_000_016, "Татьяна Угловой", "tanya_corner"),
    (900_000_017, "Максим Либеро", "max_libero"),
    (900_000_018, "Вера Номер 10", "vera_playmaker"),
    (900_000_019, "Кирилл Прессинг", "kirill_press"),
    (900_000_020, "София Волна", "sofia_wave"),
]


def seed():
    db_path = Path(__file__).resolve().parent.parent / "sqlite.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tournament = cursor.execute(
        "SELECT id, name FROM tournament WHERE id = ?", (TOURNAMENT_ID,)
    ).fetchone()
    if not tournament:
        raise SystemExit(f"Турнир id={TOURNAMENT_ID} не найден")

    created_users = 0
    created_players = 0

    for telegram_id, name, username in TEST_USERS:
        existing = cursor.execute(
            "SELECT id FROM user WHERE telegram_id = ? OR username = ?",
            (telegram_id, username),
        ).fetchone()
        if existing:
            user_id = existing[0]
        else:
            cursor.execute(
                "INSERT INTO user (name, username, telegram_id) VALUES (?, ?, ?)",
                (name, username, telegram_id),
            )
            user_id = cursor.lastrowid
            created_users += 1

        player = cursor.execute(
            "SELECT id FROM player WHERE user_id = ? AND tournament_id = ?",
            (user_id, TOURNAMENT_ID),
        ).fetchone()
        if not player:
            cursor.execute(
                'INSERT INTO player (points, "group", tournament_id, is_eliminated, user_id) '
                "VALUES (0, NULL, ?, 0, ?)",
                (TOURNAMENT_ID, user_id),
            )
            created_players += 1

    conn.commit()
    total_players = cursor.execute(
        "SELECT COUNT(*) FROM player WHERE tournament_id = ?", (TOURNAMENT_ID,)
    ).fetchone()[0]
    conn.close()

    print(f"Турнир: {tournament[1]} (id={TOURNAMENT_ID})")
    print(f"Новых пользователей: {created_users}")
    print(f"Новых игроков в турнире: {created_players}")
    print(f"Всего игроков в турнире: {total_players}")


if __name__ == "__main__":
    seed()
