import os
import random
from typing import List, Tuple

import mysql.connector
import tqdm


def generate_random_data(num_rows: int) -> Tuple[List[tuple]]:
    # Stadium data
    locations = [
        "Raith Rovers",
        "Ayr United",
        "East Fife",
        "Queen's Park",
        "Stirling Albion",
        "Arbroath",
        "Alloa Athletic",
        "Peterhead",
        "Brechin City",
    ]
    stadium_names = [
        "Stark's Park",
        "Somerset Park",
        "Bayview Stadium",
        "Hampden Park",
        "Forthbank Stadium",
        "Gayfield Park",
        "Recreation Park",
        "Balmoor",
        "Glebe Park",
    ]

    # Singer data
    singer_names = [
        "Joe Sharp",
        "Timbaland",
        "Justin Brown",
        "Rose White",
        "John Nizinik",
        "Tribal King",
    ]
    countries = ["Netherlands", "United States", "France"]
    songs = ["You", "Dangerous", "Hey Oh", "Sun", "Gentleman", "Love"]

    # Concert data
    concert_names = ["Super bootcamp", "Home Visits", "Week 2"]
    themes = [
        "Free choice",
        "Bleeding Love",
        "Wide Awake",
        "Happy Tonight",
        "Party All Night",
    ]

    stadium_data = []
    singer_data = []
    concert_data = []
    singer_concert_data = []

    # Generate stadium data
    for _ in tqdm.tqdm(range(35020, num_rows)):
        stadium_id = random.randint(11, 100)
        capacity = random.randint(2000, 60000)
        highest = random.randint(500, capacity)
        lowest = random.randint(100, highest)
        average = random.randint(lowest, highest)
        stadium_data.append(
            (
                _,
                random.choice(locations),
                random.choice(stadium_names),
                capacity,
                highest,
                lowest,
                average,
            )
        )

    # Generate singer data
    # Singer_ID 7+ (seed data is 1-6)
    for i in tqdm.tqdm(range(7, num_rows)):
        singer_data.append(
            (
                i,
                random.choice(singer_names),
                random.choice(countries),
                random.choice(songs),
                str(random.randint(1990, 2023)),
                random.randint(20, 60),
                random.choice([True, False]),
            )
        )

    # Generate concert data
    # concert_ID 7+ (seed data is 1-6)
    # Stadium_ID from seed (1-7,9,10; no 8 in seed) + generated (35020~num_rows-1)
    valid_stadium_ids = [1, 2, 3, 4, 5, 6, 7, 9, 10] + list(range(35020, num_rows))
    for i in tqdm.tqdm(range(7, num_rows)):
        concert_data.append(
            (
                i,
                random.choice(concert_names),
                random.choice(themes),
                random.choice(valid_stadium_ids),
                str(random.randint(2010, 2023)),
            )
        )

    # Generate singer_in_concert data
    # (concert_ID, Singer_ID) is PK, so deduplicate
    valid_singer_ids = list(range(1, 7)) + list(range(7, num_rows))
    valid_concert_ids = list(range(1, 7)) + list(range(7, num_rows))
    seen_pairs = set()
    for concert_id in tqdm.tqdm(valid_concert_ids):
        num_singers = random.randint(1, 3)
        selected = random.sample(valid_singer_ids, min(num_singers, len(valid_singer_ids)))
        for singer_id in selected:
            pair = (concert_id, singer_id)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                singer_concert_data.append(pair)

    return stadium_data, singer_data, concert_data, singer_concert_data


def insert_to_mysql(
    data: Tuple[List[tuple]],
    user: str = "root",
    password: str = "password",
    unix_socket: str = "/var/run/mysqld/mysqld.sock",
) -> None:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    sql_file_path = os.path.join(_SCRIPT_DIR, "concert_singer.sql")

    try:
        conn = mysql.connector.connect(
            user=user,
            password=password,
            database="concert_singer",
            unix_socket=unix_socket,
        )
    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            conn = mysql.connector.connect(
                user=user,
                password=password,
                unix_socket=unix_socket,
            )
            cursor = conn.cursor()
            with open(sql_file_path, "r") as f:
                for result in cursor.execute(f.read(), multi=True):
                    if result.with_rows:
                        print(f"Executed: {result.statement}")
            conn.database = "concert_singer"
        else:
            raise
    cursor = conn.cursor()

    stadium_data, singer_data, concert_data, singer_concert_data = data
    batch_size = 1000

    try:
        # 1. Stadium
        for i in tqdm.tqdm(range(0, len(stadium_data), batch_size), desc="stadium"):
            batch = stadium_data[i : i + batch_size]
            cursor.executemany(
                """
                INSERT INTO stadium (Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
                batch,
            )
            conn.commit()

        # 2. Singer (no FK dependency)
        for i in tqdm.tqdm(range(0, len(singer_data), batch_size), desc="singer"):
            batch = singer_data[i : i + batch_size]
            cursor.executemany(
                """
                INSERT INTO singer (Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
                batch,
            )
            conn.commit()

        # 3. Concert (FK → stadium)
        for i in tqdm.tqdm(range(0, len(concert_data), batch_size), desc="concert"):
            batch = concert_data[i : i + batch_size]
            cursor.executemany(
                """
                INSERT INTO concert (concert_ID, concert_Name, Theme, Stadium_ID, Year)
                VALUES (%s, %s, %s, %s, %s)
            """,
                batch,
            )
            conn.commit()

        # 4. Singer_in_concert (FK → concert, singer)
        for i in tqdm.tqdm(range(0, len(singer_concert_data), batch_size), desc="singer_in_concert"):
            batch = singer_concert_data[i : i + batch_size]
            cursor.executemany(
                """
                INSERT INTO singer_in_concert (concert_ID, Singer_ID)
                VALUES (%s, %s)
            """,
                batch,
            )
            conn.commit()
    finally:
        cursor.close()
        conn.close()


# Generate and insert data
random_data = generate_random_data(500_000)
insert_to_mysql(random_data)
