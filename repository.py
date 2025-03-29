import json
import logging
from datetime import datetime, timedelta
from enum import StrEnum

from database import conn, cursor

logger = logging.getLogger(__name__)


class Day(StrEnum):
    saturday = "sat"
    sunday = "sun"


def current_key():
    # Get today's date
    today = datetime.today()

    # Check if today is Sunday
    if today.weekday() == 6:  # 6 means Sunday
        # If today is Sunday, output yesterday (Saturday)
        nearest_saturday = today - timedelta(days=1)
    else:
        # Calculate the next Saturday
        days_until_saturday = (5 - today.weekday()) % 7  # 5 is Saturday's weekday value
        nearest_saturday = today + timedelta(days=days_until_saturday)

    return nearest_saturday.strftime("%Y-%m-%d")


class Poll:
    def __init__(
        self, group_chat_id: int, dt_key: str, created_by: int, group_name: str
    ):
        self.group_chat_id = group_chat_id
        self.dt_key = dt_key
        self.created_by = created_by
        self.group_name = group_name

    def update_vote(self, user_id: int, vote: set, day: Day) -> None:
        vote_str = json.dumps(list(vote))
        update_query = f"""
            UPDATE user_poll
            SET {day}_vote = ?
            WHERE dt_key = ? AND user_id = ? AND group_chat_id = ?
        """

        cursor.execute(
            update_query, (vote_str, self.dt_key, user_id, self.group_chat_id)
        )

        if cursor.rowcount == 0:
            print(
                f"No matching record found for user_id {user_id} and dt_key {self.dt_key}"
            )
        else:
            print(f"Updated vote for user_id {user_id} on dt_key {self.dt_key}")

        conn.commit()

    def get_vote(self, user_id: int, day: Day) -> set[str]:
        query = f"""
            SELECT {day}_vote 
            FROM user_poll 
            WHERE dt_key = ? AND user_id = ? AND group_chat_id = ?
        """

        cursor.execute(query, (self.dt_key, user_id, self.group_chat_id))
        result = cursor.fetchone()

        vote_str = result[0] if result else "[]"
        return set(json.loads(vote_str))

    def get_wip_day(self, user_id) -> Day:
        query = """
            SELECT sat_ready, sun_ready 
            FROM user_poll 
            WHERE dt_key = ? AND user_id = ? AND group_chat_id = ?
        """

        cursor.execute(query, (self.dt_key, user_id, self.group_chat_id))
        result = cursor.fetchone()

        if not result[0]:
            return Day.saturday

        if not result[1]:
            return Day.sunday

        logger.warning("Both days are ready, but he getting WIP day!!!")

        raise Exception("Both days are ready, but he getting WIP day!!!")

    def get_all_votes(self) -> dict[Day, list[tuple[int, set[str]]]]:
        query = """
            SELECT user_id, sat_vote, sun_vote 
            FROM user_poll 
            WHERE dt_key = ? AND group_chat_id = ?
        """

        cursor.execute(query, (self.dt_key, self.group_chat_id))
        results = cursor.fetchall()

        all_sat_votes = []
        for row in results:
            user_id = row[0]
            vote_str = row[1] if row[1] else "[]"
            vote_set = set(json.loads(vote_str))
            all_sat_votes.append((user_id, vote_set))

        all_sun_votes = []
        for row in results:
            user_id = row[0]
            vote_str = row[2] if row[2] else "[]"
            vote_set = set(json.loads(vote_str))
            all_sun_votes.append((user_id, vote_set))

        return {
            Day.saturday: all_sat_votes,
            Day.sunday: all_sun_votes,
        }

    def set_pending_users(self, user_ids: set[int]) -> None:
        insert_query = "INSERT INTO user_poll (user_id, dt_key, group_chat_id, sat_vote, sun_vote) VALUES (?, ?, ?, ?, ?)"

        for user_id in user_ids:
            cursor.execute(
                insert_query, (user_id, self.dt_key, self.group_chat_id, "[]", "[]")
            )
        conn.commit()

        print(f"Added {len(user_ids)} users to poll {self.dt_key}")

    def get_pending_users(self) -> set[int]:
        query = """
            SELECT user_id
            FROM user_poll
            WHERE dt_key = ? AND group_chat_id = ? AND (sat_ready = 0 OR sun_ready = 0)
        """

        cursor.execute(query, (self.dt_key, self.group_chat_id))
        results = cursor.fetchall()

        pending_users_set = {row[0] for row in results}

        return pending_users_set

    def set_poll_ready(self, user_id: int, day: Day):
        update_query = f"""
            UPDATE user_poll
            SET {day}_ready = true
            WHERE dt_key = ? AND user_id = ? AND group_chat_id = ?
        """

        cursor.execute(update_query, (self.dt_key, user_id, self.group_chat_id))

        if cursor.rowcount == 0:
            print(
                f"No matching record found for user_id {user_id} and dt_key {self.dt_key}"
            )
        else:
            print(f"Updated vote for user_id {user_id} on dt_key {self.dt_key}")

        conn.commit()

    def all_users_ready(self):
        query = """
            SELECT COUNT(*) 
            FROM user_poll 
            WHERE dt_key = ? AND (sat_ready = 0 OR sun_ready = 0) AND group_chat_id = ?
        """

        cursor.execute(query, (self.dt_key, self.group_chat_id))
        result = cursor.fetchone()

        if result[0] > 0:
            return False
        else:
            return True


class PollRepository:
    @staticmethod
    def new_poll(group_chat_id: int, created_by: int, group_name: str) -> Poll:
        poll = Poll(group_chat_id, current_key(), created_by, group_name)
        created_at = datetime.now()  # Get current timestamp
        cursor.execute(
            """
            INSERT INTO poll (dt_key, created_by, created_at, group_chat_id, group_name)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                poll.dt_key,
                poll.created_by,
                created_at,
                poll.group_chat_id,
                poll.group_name,
            ),
        )

        conn.commit()
        return poll

    @staticmethod
    def poll_exists(group_chat_id: int) -> bool:
        dt_key = current_key()

        cursor.execute(
            "SELECT dt_key FROM poll WHERE dt_key = ? AND group_chat_id = ?",
            (dt_key, group_chat_id),
        )
        poll = cursor.fetchone()
        return poll is not None

    @staticmethod
    def get_poll(group_chat_id: int) -> Poll:
        dt_key = current_key()

        cursor.execute(
            "SELECT created_by, group_name FROM poll WHERE dt_key = ? AND group_chat_id = ?",
            (dt_key, group_chat_id),
        )
        poll_data = cursor.fetchone()

        if poll_data is None:
            print(f"No poll found with id {dt_key}")
            raise Exception(f"No poll found with id {dt_key}")

        created_by, group_name = poll_data

        poll = Poll(
            group_chat_id=group_chat_id,
            dt_key=dt_key,
            created_by=created_by,
            group_name=group_name,
        )

        return poll

    @staticmethod
    def clear_current_poll(group_chat_id: int) -> None:
        dt_key = current_key()
        cursor.execute(
            """
            DELETE FROM user_poll 
            WHERE dt_key = ? AND group_chat_id = ?
        """,
            (dt_key, group_chat_id),
        )

        cursor.execute(
            """
            DELETE FROM poll 
            WHERE group_chat_id = ? AND dt_key = ?
        """,
            (group_chat_id, dt_key),
        )

        conn.commit()
