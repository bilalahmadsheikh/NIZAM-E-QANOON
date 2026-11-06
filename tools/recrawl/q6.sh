cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
sed -i 's/\r$//' infra/postgres/migrations/0067_instrument_supersession.sql tools/record_instrument_supersession.py tests/test_instrument_supersession.py
.venv/bin/python -m pytest -q tests/test_instrument_supersession.py 2>&1 | tail -3
bash infra/scripts/migrate.sh 2>&1 | tail -4
.venv/bin/python tools/record_instrument_supersession.py $1
