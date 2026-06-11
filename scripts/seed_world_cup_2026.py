"""Загрузка первых 24 матчей ЧМ-2026 (1-й тур группового этапа) в БД."""

import sqlite3
from pathlib import Path

TOURNAMENT_ID = 1
TOUR_ID = 1
TOUR_DEADLINE = "2026-06-11 18:00:00"

# 1-й тур группового этапа ЧМ-2026, порядок как на FIFA (11–18 июня 2026)
MATCHES = [
    ("Мексика", "ЮАР"),
    ("Южная Корея", "Чехия"),
    ("Канада", "Босния и Герцеговина"),
    ("США", "Парагвай"),
    ("Катар", "Швейцария"),
    ("Бразилия", "Марокко"),
    ("Гаити", "Шотландия"),
    ("Австралия", "Турция"),
    ("Германия", "Кюрасао"),
    ("Нидерланды", "Япония"),
    ("Кот-д'Ивуар", "Эквадор"),
    ("Швеция", "Тунис"),
    ("Испания", "Кабо-Верде"),
    ("Бельгия", "Египет"),
    ("Саудовская Аравия", "Уругвай"),
    ("Иран", "Новая Зеландия"),
    ("Франция", "Сенегал"),
    ("Ирак", "Норвегия"),
    ("Аргентина", "Алжир"),
    ("Австрия", "Иордания"),
    ("Португалия", "ДР Конго"),
    ("Англия", "Хорватия"),
    ("Гана", "Панама"),
    ("Узбекистан", "Колумбия"),
]


def seed():
    db_path = Path(__file__).resolve().parent.parent / "sqlite.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE tournament SET name = ?, competition_official_name = ?, current_tour_id = ? WHERE id = ?",
        ("Чемпионат мира по футболу 2026", "FIFA World Cup 2026", TOUR_ID, TOURNAMENT_ID),
    )
    cursor.execute(
        "UPDATE tour SET number = 1, next_deadline = ? WHERE id = ?",
        (TOUR_DEADLINE, TOUR_ID),
    )

    cursor.execute(
        "DELETE FROM match_prediction WHERE match_id IN (SELECT id FROM match WHERE tournament_id = ?)",
        (TOURNAMENT_ID,),
    )
    cursor.execute("DELETE FROM match WHERE tournament_id = ?", (TOURNAMENT_ID,))

    cursor.executemany(
        "INSERT INTO match (first_team, second_team, tour_id, tournament_id) VALUES (?, ?, ?, ?)",
        [(first, second, TOUR_ID, TOURNAMENT_ID) for first, second in MATCHES],
    )

    user = cursor.execute("SELECT id FROM user LIMIT 1").fetchone()
    if user:
        user_id = user[0]
        cursor.execute("DELETE FROM group_history WHERE tournament_id = ?", (TOURNAMENT_ID,))
        cursor.execute(
            "INSERT INTO group_history (group_distribution, timestamp, tournament_id) VALUES (?, datetime('now'), ?)",
            ('{"Group 1": [], "Group 2": []}', TOURNAMENT_ID),
        )
        existing_player = cursor.execute(
            "SELECT id FROM player WHERE user_id = ? AND tournament_id = ?",
            (user_id, TOURNAMENT_ID),
        ).fetchone()
        if existing_player:
            player_id = existing_player[0]
            cursor.execute(
                'UPDATE player SET "group" = ? WHERE id = ?',
                ("Group 1", player_id),
            )
        else:
            cursor.execute(
                'INSERT INTO player (user_id, tournament_id, "group", points, is_eliminated) VALUES (?, ?, ?, 0, 0)',
                (user_id, TOURNAMENT_ID, "Group 1"),
            )
            player_id = cursor.execute("SELECT last_insert_rowid()").fetchone()[0]
        cursor.execute(
            "UPDATE group_history SET group_distribution = ? WHERE tournament_id = ?",
            (f'{{"Group 1": [{player_id}], "Group 2": []}}', TOURNAMENT_ID),
        )
        match_ids = [
            row[0]
            for row in cursor.execute(
                "SELECT id FROM match WHERE tournament_id = ? AND tour_id = ? ORDER BY id LIMIT 12",
                (TOURNAMENT_ID, TOUR_ID),
            ).fetchall()
        ]
        cursor.execute(
            "DELETE FROM match_prediction WHERE player_id = ?",
            (player_id,),
        )
        cursor.executemany(
            "INSERT INTO match_prediction (match_id, player_id, first_team_score, second_team_score, points, is_calculated) VALUES (?, ?, 0, 0, 0, 0)",
            [(match_id, player_id) for match_id in match_ids],
        )

    conn.commit()
    count = cursor.execute(
        "SELECT COUNT(*) FROM match WHERE tournament_id = ? AND tour_id = ?",
        (TOURNAMENT_ID, TOUR_ID),
    ).fetchone()[0]
    conn.close()
    print(f"Турнир обновлён. Добавлено матчей: {count}")


if __name__ == "__main__":
    seed()
