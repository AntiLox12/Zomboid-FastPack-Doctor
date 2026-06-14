ZOMBOID FASTPACK DOCTOR - WINDOWS COMPANION 0.1.0

БЫСТРЫЙ ЗАПУСК

Запустите RUN_FASTPACK_DOCTOR.bat двойным щелчком.

Сканер автоматически определяет:
- Steam и Project Zomboid;
- Workshop-контент игры 108600;
- активный профиль модов Build 42;
- локальные моды;
- console.txt;
- runtime-отчёт FastPack.

Результаты записываются в:
outputs\fastpack-report\

Откройте fastpack-report.html в браузере.

Созданный fastpack-safe-mode.txt является только диагностическим
предложением. Программа никогда не заменяет активный профиль автоматически.

КОМАНДНАЯ СТРОКА

FastPackDoctor.exe scan --safe-mode
FastPackDoctor.exe scan --baseline "путь\к\fastpack-report.json"
FastPackDoctor.exe scan --server-ini "путь\к\servertest.ini"

Проект и обновления:
https://github.com/AntiLox12/Zomboid-FastPack-Doctor

