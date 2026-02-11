export interface QuestionSqlPair {
  qid: number;
  question: string;
  sql: string;
  execution_time: number;
}

export interface TuningResultPair extends Omit<QuestionSqlPair, 'execution_time_after_tuning'> {
  execution_time_after_tuning: number;  // Required in tuning results
}