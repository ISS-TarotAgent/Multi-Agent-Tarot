from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import pymysql


class TarotRepository:
    """Repository layer for tarot deck / spread / draw persistence."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self._config = {
            "host": host or os.getenv("DB_HOST", "mysql"),
            "port": int(port or os.getenv("DB_PORT", "3306")),
            "user": user or os.getenv("DB_USER", "tarot_user"),
            "password": password or os.getenv("DB_PASSWORD", "tarot_password"),
            "database": database or os.getenv("DB_NAME", "ai_tarot"),
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "autocommit": True,
        }

    def _get_conn(self):
        return pymysql.connect(**self._config)

    def get_spread_by_code(self, spread_code: str) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT id, spread_code, spread_name, description, card_count
        FROM spreads
        WHERE spread_code = %s AND is_active = 1
        LIMIT 1
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (spread_code,))
                return cur.fetchone()

    def get_spread_positions(self, spread_id: int) -> List[Dict[str, Any]]:
        sql = """
        SELECT position_index, label, meaning
        FROM spread_positions
        WHERE spread_id = %s
        ORDER BY position_index ASC
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (spread_id,))
                return list(cur.fetchall())

    def list_active_major_arcana_cards(self) -> List[Dict[str, Any]]:
        sql = """
        SELECT id, card_code, name_cn, name_en, arcana_type, card_number
        FROM cards
        WHERE is_active = 1 AND arcana_type = 'major'
        ORDER BY card_number ASC
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return list(cur.fetchall())

    def get_card_meaning(self, card_id: int, orientation: str, version: str = "v1") -> Optional[Dict[str, Any]]:
        sql = """
        SELECT keywords_json, core_meaning, advice, reflection_prompt
        FROM card_meanings
        WHERE card_id = %s
          AND orientation = %s
          AND version = %s
        LIMIT 1
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (card_id, orientation, version))
                row = cur.fetchone()
                if not row:
                    return None
                row["keywords"] = json.loads(row["keywords_json"])
                return row

    def create_tarot_session(
        self,
        session_id: str,
        user_question: str,
        spread_id: int,
        user_number: int,
        allow_reversed: bool,
    ) -> int:
        sql = """
        INSERT INTO tarot_sessions (
            session_code, user_question, spread_id, user_number, allow_reversed, status
        ) VALUES (%s, %s, %s, %s, %s, 'pending')
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        session_id,
                        user_question,
                        spread_id,
                        user_number,
                        1 if allow_reversed else 0,
                    ),
                )
                return cur.lastrowid

    def mark_tarot_session_completed(self, session_row_id: int) -> None:
        sql = """
        UPDATE tarot_sessions
        SET status = 'completed'
        WHERE id = %s
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (session_row_id,))

    def create_draw(
        self,
        tarot_session_id: int,
        draw_id: str,
        seed_value: str,
        deck_type: str,
        prompt_version: str,
        model_name: str,
    ) -> int:
        sql = """
        INSERT INTO draws (
            tarot_session_id, draw_code, seed_value, deck_type, prompt_version, model_name
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        tarot_session_id,
                        draw_id,
                        seed_value,
                        deck_type,
                        prompt_version,
                        model_name,
                    ),
                )
                return cur.lastrowid

    def create_draw_card(
        self,
        draw_row_id: int,
        position_index: int,
        card_id: int,
        orientation: str,
    ) -> None:
        sql = """
        INSERT INTO draw_cards (
            draw_id, position_index, card_id, orientation
        ) VALUES (%s, %s, %s, %s)
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (draw_row_id, position_index, card_id, orientation))

    def create_interpretation(
        self,
        draw_row_id: int,
        position_index: int,
        interpretation_text: str,
        structured_json: str,
    ) -> None:
        sql = """
        INSERT INTO interpretations (
            draw_id, position_index, interpretation_text, structured_json
        ) VALUES (%s, %s, %s, %s)
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (draw_row_id, position_index, interpretation_text, structured_json))