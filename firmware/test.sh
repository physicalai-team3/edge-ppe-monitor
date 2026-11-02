#!/bin/sh
# trigger 상태 머신을 PC(g++)에서 테스트한다:  docker compose --profile firmware run --rm fw sh test.sh
set -e
cd /firmware
g++ -std=c++17 -Wall -Ippe_cam -o test/test_trigger.out test/test_trigger.cpp ppe_cam/trigger.cpp
./test/test_trigger.out
