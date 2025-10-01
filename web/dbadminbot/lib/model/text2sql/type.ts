export type translationInput = {
    question: string;
    db_id: string;
    analyse: boolean;
}

export type translationResult = {
    pred_sql: string;
    confidence: number;
    user_intent: string;
    analyse_result: {
        raw_input: string;
        word_attributions: number;
    }
}