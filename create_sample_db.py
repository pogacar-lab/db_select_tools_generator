"""
サンプルDB作成スクリプト
実行: python create_sample_db.py
"""
import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "./data/sample.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.executescript("""
    CREATE TABLE IF NOT EXISTS programs (
        program_name    TEXT PRIMARY KEY,
        program_name_jp TEXT NOT NULL DEFAULT '',
        description     TEXT NOT NULL DEFAULT ''
    );

    INSERT OR IGNORE INTO programs (program_name, program_name_jp, description) VALUES
        ('python_basic',    'Python基礎',           'Pythonの基本文法・データ型・制御構造を学ぶ入門コース'),
        ('python_advanced', 'Python応用',           'クラス・デコレータ・非同期処理など中級以上の内容'),
        ('flask_web',       'Flask Webアプリ開発',  'FlaskによるRESTful APIおよびWebアプリの構築'),
        ('sql_basic',       'SQL基礎',              'SELECT・JOIN・集計関数など基本的なSQL操作'),
        ('data_analysis',   'データ分析入門',       'pandasとmatplotlibを使ったデータ分析の基礎');
""")
conn.commit()
conn.close()

print(f"サンプルDB作成完了: {DB_PATH}")
print("テーブル: programs (program_name, program_name_jp, description)")
