import aiosqlite
import logging

logger = logging.getLogger(__name__)
DB_NAME = 'main_support.db'

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                topic_id INTEGER UNIQUE,
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS unban_codes (
                code TEXT PRIMARY KEY,
                user_id INTEGER,
                admin_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Счетчик заявок на разбан
        await db.execute('''
            CREATE TABLE IF NOT EXISTS appeal_counter (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                count INTEGER DEFAULT 0
            )
        ''')
        await db.execute("INSERT OR IGNORE INTO appeal_counter (id, count) VALUES (1, 0)")
        await db.commit()

async def get_or_create_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                (user_id, username, full_name)
            )
            await db.commit()
            return (user_id, username, full_name, None, 0, None)
        
        if user[1] != username or user[2] != full_name:
             await db.execute("UPDATE users SET username=?, full_name=? WHERE user_id=?", (username, full_name, user_id))
             await db.commit()
        return user

async def set_topic(user_id: int, topic_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET topic_id = ? WHERE user_id = ?", (topic_id, user_id))
        await db.commit()

async def clear_topic(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET topic_id = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_user_by_topic(topic_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id, username, full_name, is_banned FROM users WHERE topic_id = ?", (topic_id,))
        return await cursor.fetchone()

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        return res[0] == 1 if res else False

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

async def log_message(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO chat_logs (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        await db.commit()

async def get_chat_logs(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT role, content, timestamp FROM chat_logs WHERE user_id = ? ORDER BY id ASC", (user_id,))
        return await cursor.fetchall()

async def clear_chat_logs(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM chat_logs WHERE user_id = ?", (user_id,))
        await db.commit()

async def add_unban_code(code: str, user_id: int, admin_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM unban_codes WHERE user_id = ?", (user_id,))
        await db.execute("INSERT INTO unban_codes (code, user_id, admin_id) VALUES (?, ?, ?)", (code, user_id, admin_id))
        await db.commit()

async def get_unban_code(code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id, admin_id FROM unban_codes WHERE code = ?", (code,))
        return await cursor.fetchone()

async def get_appeal_id():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE appeal_counter SET count = count + 1 WHERE id = 1")
        await db.commit()
        cursor = await db.execute("SELECT count FROM appeal_counter WHERE id = 1")
        return (await cursor.fetchone())[0]