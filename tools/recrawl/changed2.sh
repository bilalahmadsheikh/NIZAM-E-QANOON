#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -At -F ' | ' -c "SELECT i.id, left(i.short_title,60), i.status, i.repealed_on, (SELECT left(short_title,60) FROM instrument x WHERE x.id=i.repealed_by_id), EXISTS(SELECT 1 FROM v_statutory_repeal_current c WHERE c.repealed_instrument_id=i.id) FROM instrument i WHERE i.id IN ('cf91561a-d6e8-4a9b-8c7f-53dc200a1a8c','fa40b4b4-0390-470a-ab86-e92586541a0c')"
