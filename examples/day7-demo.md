# Day 7: test API, Redis cache và notification nền

Day 7 dùng lại tài khoản và dữ liệu local từ `examples/day6-demo.md`. Trước khi thử cache, chạy:

```bash
docker run --detach --name taskhub-redis \
  --publish 127.0.0.1:6379:6379 \
  redis:7-alpine
export TASKHUB_REDIS_URL='redis://127.0.0.1:6379/0'
uv run fastapi dev --host 127.0.0.1 --port 8000
```

Nếu Docker báo container `taskhub-redis` đã tồn tại, dùng `docker start taskhub-redis` thay cho
`docker run`. Redis là tùy chọn: không đặt `TASKHUB_REDIS_URL` thì API vẫn trả dữ liệu từ PostgreSQL.

## Thử cache task-list

1. Login bằng `owner@taskhub.demo` hoặc `editor@taskhub.demo`, rồi Authorize trong Swagger.
2. Gọi `GET /api/v1/projects/{project_id}/tasks?status=TODO&page=1&limit=20` hai lần với cùng
   tham số.
3. Lần đầu API đọc database và lưu JSON response vào Redis trong 60 giây. Lần sau API lấy JSON
   từ Redis nhưng vẫn kiểm tra quyền workspace trước khi trả response.
4. Tạo task bằng `POST /api/v1/projects/{project_id}/tasks` hoặc gán task bằng
   `POST /api/v1/tasks/{task_id}/assign`. Lần gọi GET tiếp theo đọc database lại vì cache của
   project đã bị xóa.

Filter `status`, `priority`, `assignee_id`, `page` và `limit` đều là một phần của cache key. Vì
vậy response của trang 1 không thể bị dùng nhầm cho trang 2 hoặc filter khác.

## Thử notification nền khi gán task

Gọi `POST /api/v1/tasks/{task_id}/assign` bằng owner/editor với body:

```json
{
  "assignee_id": 3
}
```

API commit thay đổi trước, trả response `200`, rồi mới chạy notification nền. Day 7 chỉ ghi email
notification mô phỏng vào log server, không gửi email thật và không để lỗi notification làm rollback
việc gán task. Điều này giúp thay SMTP bằng một service thật sau này mà router không phải thay đổi.

## Test tự động

```bash
uv run pytest tests/test_day7_api_flow.py tests/test_task_cache.py
```

Các test mô phỏng Redis trong bộ nhớ để chạy ổn định không cần Docker. Chúng kiểm tra cache hit,
fallback khi Redis lỗi, invalidation khi mutation, notification background, và API flow đăng ký →
đăng nhập → tạo task.
