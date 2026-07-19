# TaskHub API

TaskHub là REST API quản lý công việc, được xây dựng từng ngày theo tài liệu trong `docs/`.

## Ngày 1

Đã có skeleton FastAPI async, model SQLAlchemy, Alembic và router namespace `/api/v1`.
CRUD, JWT, quan hệ ORM/eager loading, Redis và Docker sẽ được bổ sung ở các session sau.

## Chạy cục bộ

Yêu cầu: Python 3.10–3.13 và [uv](https://docs.astral.sh/uv/).

### 1. Chuẩn bị PostgreSQL 16 bằng Docker

```bash
docker run --detach --name taskhub-postgres \
  --env POSTGRES_USER=taskhub \
  --env POSTGRES_PASSWORD=taskhub \
  --env POSTGRES_DB=taskhub \
  --publish 127.0.0.1:54330:5432 \
  postgres:16-alpine
```

Nếu cổng `54330` đã được sử dụng, chọn một cổng trống khác và thay giá trị đó ở biến môi trường trong bước tiếp theo.

### 2. Cài dependencies, migrate và chạy API

```bash
uv sync --extra dev
cp .env.example .env
export TASKHUB_DATABASE_URL='postgresql+asyncpg://taskhub:taskhub@127.0.0.1:54330/taskhub'
uv run alembic upgrade head
uv run fastapi dev --host 127.0.0.1 --port 8000
```

- Health check: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

`TASKHUB_DATABASE_URL` trong `.env` phải trỏ đến PostgreSQL đang chạy trước khi chạy migration. Dừng database demo bằng `docker stop taskhub-postgres`; khởi động lại bằng `docker start taskhub-postgres`.

## Kiểm tra chất lượng

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```
