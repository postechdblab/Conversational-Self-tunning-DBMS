"use client";
import { useChatContext } from "@/context/chatContext";
import { useDatabaseContext } from "@/context/databaseContext";
import { useTuningResultContext } from "@/context/dbtuningContext";
import { useQueryResultContext } from "@/context/queryResultContext";
import { useQuestionSqlContext } from "@/context/questionSqlContext";
import { responseHeaderJson, responseMethodPost } from "@/lib/api/utils";
import { MessageType, RESET_MESSAGE } from "@/lib/message/types";
import { DBAdminBotMessageToMessageModel, filterMessagesByType, filterUserMessages } from "@/lib/message/utils";
import { useResetTranslationHistory, useTranslatedSQLByQuestion } from "@/lib/model/text2sql/get";
import { TuningResultPair } from "@/lib/model/tuning/type";
import { tunerQueryResult } from "@/lib/query/type";
import { Button, ChatContainer, MainContainer, Message, MessageInput, MessageList, MessageSeparator, SendButton, TypingIndicator } from "@chatscope/chat-ui-kit-react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import React, { useEffect, useMemo, useState } from "react";
import { BsFillEraserFill } from "react-icons/bs";
import striptags from 'striptags';

import { summarizationResult } from '@/lib/model/table2text/type';
const WELCOME_MESSAGE = "Hi, I'm DBAdminBot. I can help you to query the database using natural language. Please select a database to start.";
const SYSTEM_END_MESSAGE = "You're welcome! If you have any more questions or need further assistance, feel free to ask.";
const typingIndicator = <TypingIndicator content="DBAdminBot is thinking" />;
const SESSION_END_INTENTS = ["thank_you", "affirm"];
interface QueryResultState {
    data: tunerQueryResult | undefined;
    isTuning: boolean;
    executionTime?: number;
    queries?: string[];
    execution_times?: number[];
}

export default function ChatWindow() {
    const { messages, setMessages } = useChatContext();
    const { selectedDB } = useDatabaseContext();
    const { setQueryResult } = useQueryResultContext();
    const { questionSqlPairs, setQuestionSqlPairs } = useQuestionSqlContext();
    const { tuningResultPairs, setTuningResultPairs } = useTuningResultContext();
    const [isWaitingTranslation, setIsWaitingTranslation] = useState<boolean>(false);
    const [isWaitingSummarization, setIsWaitingSummarization] = useState<boolean>(false);
    const [isWaitingTuning, setIsWaitingTuning] = useState<boolean>(false);
    const [inputMessage, setInputMessage] = useState<string>("");
    const [resetSession, setResetSession] = useState<boolean>(false);
    const [translationHandled, setTranslationHandled] = useState<boolean>(false);
    const chatScopeMessages = useMemo(() => messages.map(DBAdminBotMessageToMessageModel), [messages]);
    const SQLMessages = useMemo(() => filterMessagesByType(messages, MessageType.isSQL), [messages]);
    const userMessages = useMemo(() => filterUserMessages(messages), [messages]);

    //3. Query and get result
    const [localQueryResult, setLocalQueryResult] = useState<QueryResultState>();
    useEffect(() => {
        // Define the key for SWR based on the dbName and query.
        // If either is not present, use null to avoid fetching.
        const query = SQLMessages[SQLMessages.length - 1]?.message;
        if (query) {
            fetch("http://localhost:1234/query", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(query),
            }).then(res => res.json()).then(j => {
                const data = j as tunerQueryResult;
                const isTuning = query == "conduct tuning";
                setLocalQueryResult({
                    data,
                    isTuning,
                    executionTime: data.execution_time,
                    queries: data.queries,
                    execution_times: data.execution_times,
                });
            });
        }
    }, [SQLMessages[SQLMessages.length - 1]?.message]);
    //2. Translate to SQL
    const translationResult = useTranslatedSQLByQuestion(selectedDB, userMessages[userMessages.length - 1]?.message, messages[messages.length - 2]?.message == RESET_MESSAGE)
    // const summarizationResult = useSummarizationFromTable(localQueryResult?.data as unknown as summarizationInput);
    // const [summarizationResult, setSummarizationResult] = useState<summarizationResult>();
    useEffect(() => {
        const rowValues = localQueryResult?.data?.data;
        if (rowValues) {
            fetch("/api/model/table2text", {
                body: JSON.stringify({
                    rowValues: rowValues,
                }),
                ...responseHeaderJson, ...responseMethodPost
            }).then(res => res.json()).then(j => {
                const data = j as summarizationResult;
                setMessages([
                    ...messages,
                    {
                        message: data.summary,
                        confidence: 100,
                        type: MessageType.isResultSummary,
                        intent: null,
                    }
                ]);
                setIsWaitingSummarization(false);
            });
        }
    }, [localQueryResult?.data?.data]);
    const tmpResetResponse = useResetTranslationHistory(resetSession);
    // const tuningResult = useDBTuning(questionSqlPairs, localQueryResult.isTuning);

    // useEffect(() => {
    //     if (tuningResult && isWaitingTuning) {
    //         console.log('tuningResult', tuningResult);
    //         setTuningResultPairs(tuningResult);
    //         setIsWaitingTuning(false);
    //     }
    //     else if (tuningResult == undefined || tuningResult == null) {
    //         setTuningResultPairs([]);
    //     }
    // }, [tuningResult, isWaitingTuning]);

    // useEffect(() => {
    //     if (
    //         translationResult?.data?.pred_sql &&
    //         userMessages?.[userMessages.length - 1]?.message
    //     ) {
    //         const isDuplicate = questionSqlPairs.some(pair =>
    //             pair.question === userMessages[userMessages.length - 1]?.message
    //         );
    //         // Check if the user message is "conduct tuning"
    //         const isConductTuning = translationResult?.data?.pred_sql === "conduct tuning";
    //         // do not add to questionSqlPairs if the user message is "conduct tuning" not or duplicate
    //         if (!isDuplicate || !translationHandled) {
    //             if (!isConductTuning) {
    //                 const newPair = {
    //                     qid: questionSqlPairs.length,
    //                     question: userMessages[userMessages.length - 1]?.message,
    //                     sql: translationResult?.data.pred_sql,
    //                     execution_time: 10
    //                 };
    //                 setQuestionSqlPairs(prevPairs => [...prevPairs, newPair]);
    //                 setTranslationHandled(true); // Mark as handled to avoid repeating
    //             }
    //         }
    //     }
    // }, [translationResult?.data?.pred_sql, userMessages, questionSqlPairs, translationHandled]);

    useEffect(() => {
        // Reset translationHandled whenever a new message is added
        if (isWaitingTranslation) {
            setTranslationHandled(false);
        }
    }, [isWaitingTranslation]);

    const messageInputOnChange = (value: string) => {
        const valueWithoutHTML = striptags(value).replace('&gt;', '>').replace('&lt;', '<');
        const valueWithoutHTML_ = valueWithoutHTML.replace(/ &nbsp;/g, ' ');
        setInputMessage(valueWithoutHTML_);
    };

    //1. Handle input
    const inputHandler = () => {
        // Make request to the backend server
        setMessages([
            ...messages,
            {
                message: inputMessage,
                confidence: 100,
                type: MessageType.isUser,
                intent: null,
            },
        ]);
        setIsWaitingTranslation(true);
        setInputMessage("");
    };

    // Reset message if the selected database is changed
    useEffect(() => {
        if (selectedDB) {
            setMessages([{
                message: WELCOME_MESSAGE,
                confidence: 100,
                type: MessageType.isSystemMessage,
                intent: null,
            }, {
                message: `You have selected "${selectedDB}" database. Please ask me a question.`,
                confidence: 100,
                type: MessageType.isSystemMessage,
                intent: null,
            }]);
        }
        else {
            setMessages([{
                message: WELCOME_MESSAGE,
                confidence: 100,
                type: MessageType.isSystemMessage,
                intent: null,
            }]);
        }
    }, [selectedDB, setMessages]);

    // unset reset session flag if the reset session response is received
    useEffect(() => {
        if (tmpResetResponse.data) {
            setResetSession(false);
        }
    }, [setResetSession, tmpResetResponse]);


    // // Add table summary message
    // useEffect(() => {
    //     // Check if last message isSQL query and query result is not empty
    //     if (isWaitingSummarization && summarizationResult && localQueryResult?.data) {
    //         // Request summarization from the backend server
    //         setMessages([
    //             ...messages,
    //             {
    //                 message: summarizationResult.summary,
    //                 confidence: 100,
    //                 type: MessageType.isResultSummary,
    //                 intent: null,
    //             }
    //         ]);
    //         setIsWaitingSummarization(false);
    //     }
    // }, [messages, setMessages, isWaitingSummarization, setIsWaitingSummarization, localQueryResult?.data, summarizationResult]);

    // Add session reset message
    useEffect(() => {
        if (resetSession) {
            setMessages([
                ...messages,
                {
                    message: RESET_MESSAGE,
                    confidence: 100,
                    type: MessageType.isSystemMessage,
                    intent: null,
                }
            ]);
            setResetSession(false);
        }
    }, [messages, setMessages, resetSession]);

    // Handle the translation response from the backend server 
    useEffect(() => {
        if (translationResult?.data && isWaitingTranslation) {
            const newMessages = [
                ...messages.slice(0, -1),
                // Correct the last user message with predicted intent
                {
                    message: messages[messages.length - 1].message,
                    confidence: 100,
                    type: MessageType.isUser,
                    intent: translationResult?.data.user_intent,
                },
            ];
            // Add system message only if the user intent is not "thank_you"
            if (SESSION_END_INTENTS.includes(translationResult?.data.user_intent)) {
                newMessages.push({
                    message: SYSTEM_END_MESSAGE,
                    confidence: 100,
                    type: MessageType.isSystemMessage,
                    intent: "none",
                });
                setResetSession(true);
            }
            else {
                newMessages.push({
                    message: translationResult?.data.pred_sql,
                    confidence: translationResult?.data.confidence,
                    type: MessageType.isSQL,
                    intent: "none",
                });
                // Add recommendation message if the confidence is low
                if (translationResult?.data.confidence < 70) {
                    newMessages.push({
                        message: `I'm not sure if I understand your question. Are you sure you mean "${translationResult?.data.analyse_result.raw_input}"?`,
                        confidence: 100,
                        type: MessageType.isSystemMessage,
                        intent: "none",
                    });
                    setIsWaitingSummarization(false);
                }
                else {
                    setIsWaitingSummarization(true);
                }
            }

            setMessages(newMessages);
            setIsWaitingTranslation(false);
        }

    }, [selectedDB, messages, setMessages, setQueryResult, translationResult?.data, isWaitingTranslation])

    // Handle the execution response from the backend server 
    //4. Set query result
    useEffect(() => {
        if (localQueryResult?.data) {
            setQueryResult(localQueryResult.data.data);
        }
        else if (localQueryResult?.data == undefined) {
            setQueryResult(null);
            if (localQueryResult?.isTuning) {
                setIsWaitingSummarization(false);
                setIsWaitingTuning(true);
            }
        }
        if (localQueryResult?.execution_times) {
            const c: TuningResultPair[] = [];
            for (let i = 0; i < localQueryResult.execution_times.length; ++i) {
                c.push({
                    execution_time_after_tuning: localQueryResult.execution_times[i],
                    execution_time: questionSqlPairs[i].execution_time,
                    qid: i,
                    question: questionSqlPairs[i].question,
                    sql: questionSqlPairs[i].sql,
                })
            }
            setTuningResultPairs(tuningResultPairs => c);
            setTranslationHandled(true); // Mark as handled to avoid repeating
            setIsWaitingTuning(false);
        }
        if (
            translationResult?.data?.pred_sql &&
            userMessages?.[userMessages.length - 1]?.message
        ) {
            const isDuplicate = questionSqlPairs.some(pair =>
                pair.question === userMessages[userMessages.length - 1]?.message
            );
            // Check if the user message is "conduct tuning"
            const isConductTuning = translationResult?.data?.pred_sql === "conduct tuning";
            // do not add to questionSqlPairs if the user message is "conduct tuning" not or duplicate
            if (!isDuplicate || !translationHandled) {
                if (localQueryResult?.executionTime) {
                    if (!isConductTuning) {
                        const newPair = {
                            qid: questionSqlPairs.length,
                            question: userMessages[userMessages.length - 1]?.message,
                            sql: translationResult?.data.pred_sql,
                            execution_time: localQueryResult.executionTime,
                        };
                        setQuestionSqlPairs(prevPairs => [...prevPairs, newPair]);
                        setTranslationHandled(true); // Mark as handled to avoid repeating
                    }
                }
            }
        }
    }, [selectedDB, setQueryResult, localQueryResult?.data, localQueryResult?.isTuning, localQueryResult?.execution_times]);

    return (
        <React.Fragment>
            <div style={{ position: "relative", height: "500px", paddingLeft: "20px", paddingRight: "20px" }}>
                <MainContainer>
                    <ChatContainer>
                        <MessageList typingIndicator={isWaitingTranslation || isWaitingSummarization ? typingIndicator : null}>
                            {chatScopeMessages.map((message, idx) => (
                                message.message == RESET_MESSAGE
                                    ?
                                    <MessageSeparator key={idx} content="End of session" />
                                    :
                                    <Message key={idx} model={message} >
                                        <Message.Footer sentTime={message.sentTime} />
                                    </Message>

                            ))}
                        </MessageList>

                        {/* My own style message input component */}
                        <div is={"MessageInput"}
                            style={{
                                display: "flex",
                                flexDirection: "row",
                                borderTop: "1px dashed #d1dbe4"
                            }}>
                            <MessageInput
                                style={{
                                    flexGrow: 1,
                                    borderTop: 0,
                                    flexShrink: "initial"
                                }}
                                placeholder="Natural Language Query"
                                value={inputMessage}
                                onChange={messageInputOnChange}
                                onSend={inputHandler}
                                sendButton={false} attachButton={false} />
                            <SendButton
                                style={{
                                    fontSize: "1.2em",
                                    marginLeft: 0,
                                    paddingLeft: "0.2em",
                                    paddingRight: "0.2em"
                                }}
                                onClick={inputHandler}
                                disabled={false} />
                            <Button
                                style={{
                                    fontSize: "1.2em",
                                    marginLeft: 0,
                                    paddingLeft: "0.2em",
                                    paddingRight: "0.2em"
                                }}
                                onClick={() => setResetSession(true)}>
                                <BsFillEraserFill />
                            </Button>
                        </div>
                    </ChatContainer>
                </MainContainer>
            </div>
        </React.Fragment>
    );
}

