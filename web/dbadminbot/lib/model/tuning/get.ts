'use client';
// input: questionSqlPairs from chatWindow
import { QuestionSqlPair, TuningResultPair } from '@/lib/model/tuning/type';

export function useDBTuning(questionSqlPairs: QuestionSqlPair[], isTuning: boolean): TuningResultPair[] | null {
    // Dummy data for now
    if (isTuning) {
        const dummy_questionSqlPairs = questionSqlPairs.map(pair => ({
            ...pair,
            execution_time_after_tuning: pair.execution_time * 0.5
        })) as TuningResultPair[];
        return dummy_questionSqlPairs;
    }
    else {
        return null;
    }
}