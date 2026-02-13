Objective: 대화 가능하고 자동으로 튜닝하는 DBMS 개발 이라는 과제를 수행한 결과 DBAdminBot과 EDAframework를 만들게 되었다. 이에 대한 데모를 포함한 github repository의 readme를 영어로 professional하게 작성하고자 한다. 다음의 요소들이 readme에 들어갔으면 좋겠고, section의 순서나 내용은 professional하고 readable하고 top down으로 사용자가 받아들이기 쉽게 변경해도 된다.


# 과제 소개:
과제 전체 기간 목표: 대화 가능하고 자동으로 튜닝하는 DBMS 개발
1단계(2018년~2021년) 주요 개발 목표:
- 연속 대화형 자연 언어 질의 처리 기술
2단계(2022년~2023년) 주요 개발 목표:
- 질의 결과에 대한 자연어 생성 기술
- 신뢰도 기반 자연어 질의 해명 요구 기술
- 성능 이상 탐지 및 원인 분석 기술
3단계(2024년~2025년) 주요 개발 목표: DBMS 환경 설정 자동 튜닝 및 성능 이상 해결 기술

# 이 repository에는 code가 없지만, 수행하고 있는 과제와 관련된 다른 코드들의 link들 (@related_works.md 를 참조하여 readme에 작성해라. 실제로는 hyperlink로 다 걸어두고 있어야 한다. 각각이 몇개의 star, commit, fork, contributor의 수가 있는지 아예 표로 나타내면 좋을 것 같다.)

# 과제에 align되는 구현 내용 소개:
DBAdminBot에서 지원하는 기능:
- 연속 대화형 NL2SQL (1단계)
- Schema 시각화
- SQL 수행 결과 시각화 및 자연어 생성 (2단계)
- 신뢰도 기반 자연어 질의 해명 요구 기술 (2단계)
- Workload history 시각화
- Knob tuning 수행 (3단계): 사용자가 대화형 인터페이스로 DBMS 최적화 요청시 knob tuning 진행
- Knob tuning 결과 시각화 (3단계): Knob tuning을 수행한 이후 knob과 질의 수행속도 변화를 시각화

EDAframework에서 지원하는 기능:
- DB 성능 이상 탐지 및 원인 분석 기술

# 코드 구조 소개:

# 데모를 수행하기 위한 세팅 과정 (docker compose up -d 부터 어떤 command들을 수행하면 데모가 수행되는지 (각 데모마다 end-to-end로 수행되는 bash script를 만들어서 이를 실행하라고 readme에 작성하는 것이 좋을 것 같다.)) 그리고 어떤 폴더들이 mount되어야 하는지.

## DBAdminBot

## EDAframework


위와 같은 readme를 작성하기 위해 필요한 정보들을 수집하고, readme를 professional하게 작성하기 위한 계획을 작성해라.