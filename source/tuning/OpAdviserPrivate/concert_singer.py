import random
from typing import List, Tuple

import mysql.connector
import psycopg2
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

    # # Generate singer data
    # for _ in range(num_rows):
    #     singer_data.append(
    #         (
    #             random.randint(7, 100),
    #             random.choice(singer_names),
    #             random.choice(countries),
    #             random.choice(songs),
    #             str(random.randint(1990, 2023)),
    #             random.randint(20, 60),
    #             random.choice([True, False]),
    #         )
    #     )

    # Generate concert data
    # for _ in tqdm.tqdm(range(22_000_000, num_rows)):
    #     concert_data.append(
    #         (
    #             _,
    #             random.choice(concert_names),
    #             random.choice(themes),
    #             random.randint(1, 7),
    #             str(random.randint(2010, 2023)),
    #         )
    #     )

    # Generate singer_in_concert data
    # for _ in range(num_rows):
    #     singer_concert_data.append((random.randint(1, 10), random.randint(1, 6)))

    return stadium_data, singer_data, concert_data, singer_concert_data


def insert_to_mysql(data: Tuple[List[tuple]]) -> None:
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="password",
            database="concert_singer",
            port=3306,
        )
    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="password",
                port=3306,
            )
            cursor = conn.cursor()
            with open("/workspaces/OpAdviserPrivate/concert_singer.sql", "r") as f:
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
        for i in tqdm.tqdm(range(0, len(stadium_data), batch_size)):
            # batch = concert_data[i : i + batch_size]
            # cursor.executemany(
            #     """
            #     INSERT INTO concert (concert_ID, concert_Name, Theme, Stadium_ID, Year)
            #     VALUES (%s, %s, %s, %s, %s)
            # """,
            #     batch,
            # )
            batch = stadium_data[i : i + batch_size]
            cursor.executemany(
                """
                INSERT INTO stadium (Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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
