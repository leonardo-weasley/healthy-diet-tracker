import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


class Config:
    @staticmethod
    def values():
        load_dotenv(ROOT / '.env')
        maximum = int(os.getenv('UPLOAD_MAX_BYTES', '8388608'))
        return dict(
            APP_HOST=os.getenv('APP_HOST', '127.0.0.1'),
            APP_PORT=int(os.getenv('APP_PORT', '5000')),
            APP_DEBUG=os.getenv('APP_DEBUG', 'false').lower() == 'true',
            APP_TIMEZONE=os.getenv('APP_TIMEZONE', 'Asia/Shanghai'),
            BACKEND_MODE=os.getenv('BACKEND_MODE', 'demo'),
            SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///diet_tracker.db'),
            AI_API_KEY=os.getenv('AI_API_KEY', ''),
            AI_MODEL=os.getenv('AI_MODEL', ''),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            UPLOAD_ROOT=str(ROOT), UPLOAD_MAX_BYTES=maximum,
            # Allow multipart boundaries in addition to the file's exact limit.
            MAX_CONTENT_LENGTH=maximum + 1024 * 1024,
            UPLOAD_MAX_SIDE=int(os.getenv('UPLOAD_MAX_SIDE', '1024')),
        )
