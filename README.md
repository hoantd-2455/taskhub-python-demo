# TaskHub API

TaskHub là REST API quản lý công việc, được xây dựng từng ngày theo tài liệu trong `docs/`.

## Tiến độ ngày 1–8

Đã có skeleton FastAPI async, model SQLAlchemy, Alembic, CRUD đọc cơ bản, quan hệ ORM/eager
loading và xác thực JWT dưới namespace `/api/v1`. Day 4 bổ sung đăng ký, OAuth2 login, access
token, refresh token có thể thu hồi, logout và các endpoint hồ sơ của người dùng. Day 5 bổ sung
RBAC workspace cho task, filtering và pagination. Day 6 bổ sung gán người phụ trách, bình luận
và rollback transaction khi thao tác dữ liệu thất bại. Day 7 bổ sung cache Redis cho danh sách
task theo project, invalidation sau khi task thay đổi và notification nền khi gán task.
Day 8 hoàn thiện Workspace/Project/Task/Label API, CORS, logging và Docker Compose.

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
export TASKHUB_JWT_SECRET_KEY="$(openssl rand -hex 32)"
uv run alembic upgrade head
uv run python scripts/seed_example_data.py
uv run fastapi dev --host 127.0.0.1 --port 8000
```

- Health check: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Lệnh `export TASKHUB_JWT_SECRET_KEY="$(openssl rand -hex 32)"` tự tạo chuỗi bí mật hợp lệ và
không cần sao chép thủ công. Hai lệnh `export` chỉ có hiệu lực trong terminal hiện tại; để dùng ở
terminal khác, chạy lại chúng hoặc thay hai giá trị tương ứng trong `.env`. Không commit `.env`.
Dừng database demo bằng `docker stop taskhub-postgres`; khởi động lại bằng
`docker start taskhub-postgres`.

### 3. Bật Redis cho cache Day 7 (tùy chọn)

API vẫn hoạt động khi không có Redis, chỉ không cache danh sách task. Để bật cache local:

```bash
docker run --detach --name taskhub-redis \
  --publish 127.0.0.1:6379:6379 \
  redis:7-alpine
export TASKHUB_REDIS_URL='redis://127.0.0.1:6379/0'
```

Sau đó gọi cùng một `GET /api/v1/projects/{project_id}/tasks` hai lần với cùng filter và
phân trang: lần đầu đọc PostgreSQL, lần sau đọc Redis. Tạo task hoặc gán người phụ trách sẽ xóa
toàn bộ cache task-list của project đó. Khi gán task, ứng dụng chạy background task ghi một email
notification mô phỏng vào log; chưa kết nối SMTP thật trong Day 7.

### 4. Chạy toàn bộ stack bằng Docker Compose

Đây là cách phù hợp nhất để chạy bản hoàn chỉnh gồm API, PostgreSQL và Redis:

```bash
uv sync --extra dev
export TASKHUB_JWT_SECRET_KEY="$(openssl rand -hex 32)"
export TASKHUB_POSTGRES_PASSWORD='a-local-postgres-password'
docker compose up --build
```

API sẽ tự chạy Alembic migration sau khi PostgreSQL sẵn sàng. Mở
`http://127.0.0.1:8000/docs` để thử Swagger. Trong terminal khác, tạo dữ liệu local tùy chọn:

```bash
docker compose exec app uv run --no-sync python scripts/seed_example_data.py
```

Dừng stack bằng `docker compose down`; thêm `--volumes` chỉ khi bạn muốn xóa cả dữ liệu database
demo. Compose nhận JWT từ biến môi trường hiện tại; để dùng ở lần chạy sau, lưu một giá trị ngẫu
nhiên tối thiểu 32 ký tự cùng `TASKHUB_POSTGRES_PASSWORD` vào `.env` (file này không được commit).

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

## Dữ liệu mẫu Day 5–6

Sau migration, tạo dữ liệu mẫu để thực hành trên Swagger:

```bash
uv run python scripts/seed_example_data.py
```

Xem tài khoản giả, ví dụ filter/pagination và các tình huống RBAC tại
[`examples/day5-demo.md`](examples/day5-demo.md), cùng các luồng gán task/bình luận tại
[`examples/day6-demo.md`](examples/day6-demo.md), và cache/notification tại
[`examples/day7-demo.md`](examples/day7-demo.md), cùng Docker/CRUD đầy đủ tại
[`examples/day8-demo.md`](examples/day8-demo.md). Không dùng các tài khoản demo này ngoài môi trường local.

## Kiểm tra chất lượng

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```
