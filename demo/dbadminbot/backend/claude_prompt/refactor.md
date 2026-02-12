Objective: @backend_server.py 가 source의 모델들을 사용하도록 @backend_server_v2.py 에 refactoring하는 것이다.

다음의 요구사항을 지켜야 한다.

- @backend_server.py 의 /text_to_sql, /table_to_text, /reset_history, / 가 각각 현재 script상에 지원되는 입력과 동일한 입력에 대해 지원되어야 한다.
- tuning intent 혹은 query intent에 대해서는 @source/text2intent/intent_inferer.py 의 IntentInferer를 활용한다.
- /table_to_text 에 대해서는 @source/conversation/table2text/table_to_text.py 의 Table2Text class를 활용한다.
- text to sql 을 수행해야 할 때는 @source/text2sql/text_to_sql.py 의 Text2SQL class를 사용하고, confidence를 계산해야하는 것에 대해서는  @source/conversation/text2confidence/text_to_confidence.py 의 Text2Confidence class를 활용한다.
- Cache가 지원되도록 redis도 지원되어야 한다.

위를 수행할 수 있는 상세한 계획을 작성하여 공유해라.

