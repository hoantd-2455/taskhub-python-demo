# TaskHub API

TaskHub là REST API quản lý công việc, được xây dựng từng ngày theo tài liệu trong `docs/`.

## Tiến độ ngày 1–5

Đã có skeleton FastAPI async, model SQLAlchemy, Alembic, CRUD đọc cơ bản, quan hệ ORM/eager
loading và xác thực JWT dưới namespace `/api/v1`. Day 4 bổ sung đăng ký, OAuth2 login, access
token, refresh token có thể thu hồi, logout và các endpoint hồ sơ của người dùng. Day 5 bổ sung
RBAC workspace cho task, filtering và pagination.

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
openssl rand -hex 32
export TASKHUB_DATABASE_URL='postgresql+asyncpg://taskhub:taskhub@127.0.0.1:54330/taskhub'
export TASKHUB_JWT_SECRET_KEY='paste-the-random-value-here'
uv run alembic upgrade head
uv run fastapi dev --host 127.0.0.1 --port 8000
```

- Health check: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Thay chuỗi mẫu `TASKHUB_JWT_SECRET_KEY` trong `.env` bằng giá trị do `openssl rand -hex 32` tạo
ra; không commit file `.env`. `TASKHUB_DATABASE_URL` trong `.env` phải trỏ đến PostgreSQL đang
chạy trước khi chạy migration. Dừng database demo bằng `docker stop taskhub-postgres`; khởi động
lại bằng `docker start taskhub-postgres`.

## Thử luồng xác thực Day 4

1. Mở `http://127.0.0.1:8000/docs`, gọi `POST /api/v1/auth/register` với email, `full_name` và
   mật khẩu tối thiểu 8 ký tự.
2. Ở `POST /api/v1/auth/login`, nhập email vào trường `username` của OAuth2 và nhập mật khẩu.
   Response trả về `access_token` và `refresh_token`.
3. Nhấn **Authorize** trong Swagger, dán access token (không dán refresh token), rồi gọi
   `GET /api/v1/users/me` hoặc `PATCH /api/v1/users/me`.
4. Dùng `POST /api/v1/auth/refresh` để đổi refresh token lấy cặp token mới. Dùng
   `POST /api/v1/auth/logout` để thu hồi refresh token hiện tại.

Access token mặc định có hạn 30 phút; refresh token có hạn 7 ngày. Có thể chỉnh hai giá trị này
trong `.env` bằng `TASKHUB_ACCESS_TOKEN_EXPIRE_MINUTES` và `TASKHUB_REFRESH_TOKEN_EXPIRE_DAYS`.

## Dữ liệu mẫu Day 5

Sau migration, tạo dữ liệu mẫu để thực hành trên Swagger:

```bash
uv run python scripts/seed_example_data.py
```

Xem tài khoản giả, ví dụ filter/pagination và các tình huống RBAC tại
[`examples/day5-demo.md`](examples/day5-demo.md). Không dùng các tài khoản demo này ngoài môi trường local.

## Kiểm tra chất lượng

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```
