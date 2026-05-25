"""Domain services — бизнес-логика которая не помещается в один route.

Сервисы создаются с минимальным количеством зависимостей (DB connection,
HTTP client) и тестируются изолированно от FastAPI.

M-K1.7: первый сервис — capability_discovery.
"""
