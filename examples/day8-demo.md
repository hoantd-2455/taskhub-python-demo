# Day 8: vận hành toàn stack và API hoàn chỉnh

Day 8 chạy ba service cùng lúc: `app` (FastAPI), `db` (PostgreSQL 16) và `redis` (Redis 7).

```bash
export TASKHUB_JWT_SECRET_KEY="$(openssl rand -hex 32)"
export TASKHUB_POSTGRES_PASSWORD='a-local-postgres-password'
docker compose up --build
```

Khi terminal hiển thị Uvicorn đang chạy, mở `http://127.0.0.1:8000/docs`. Nếu muốn dữ liệu giả:

```bash
docker compose exec app uv run --no-sync python scripts/seed_example_data.py
```

## Các nhóm API cuối cùng

| Nhóm | API chính | Quyền |
| --- | --- | --- |
| Workspace | Tạo/xem/sửa/xóa workspace; mời/xóa member | Owner hoặc admin quản lý; member được đọc |
| Project | Tạo trong workspace; sửa/archive/xóa | Owner hoặc admin |
| Task | List/create/update/delete, assign, comment | Editor/owner thao tác; viewer chỉ đọc |
| Label | CRUD label theo project; gán/bỏ label cho task | Editor/owner thao tác; viewer chỉ đọc |

Mọi URL lồng nhau đều kiểm tra workspace cha. Ví dụ, không thể gắn một label của project A cho
task của project B, kể cả khi biết ID của label đó.

## Ví dụ luồng Workspace → Project → Task

1. Đăng ký hoặc login, rồi nhấn **Authorize** trong Swagger.
2. `POST /api/v1/workspaces` với `{ "name": "Demo workspace" }`.
3. `POST /api/v1/workspaces/{workspace_id}/projects` với tên project.
4. `POST /api/v1/projects/{project_id}/tasks` để tạo task.
5. `PATCH /api/v1/tasks/{task_id}` để cập nhật status, priority, due date, mô tả hoặc assignee.
6. `POST /api/v1/projects/{project_id}/labels`, rồi
   `POST /api/v1/tasks/{task_id}/labels/{label_id}` để liên kết label.

Tạo/sửa/xóa task hoặc label sẽ xóa cache Redis của project. Request GET task-list tiếp theo đọc
database và tạo cache mới. CORS mặc định chấp nhận frontend `http://localhost:3000`; thay biến
`TASKHUB_CORS_ORIGINS` bằng JSON list trong `.env` nếu frontend chạy ở origin khác.

## Kiểm tra trước khi bàn giao

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run pytest
docker compose up --build
```
