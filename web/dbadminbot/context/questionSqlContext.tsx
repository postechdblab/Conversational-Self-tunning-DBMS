// QuestionSqlContext.tsx
"use client"; // Add this line to make the component a Client Component

import React, { createContext, useContext, useState, ReactNode } from 'react';

type QuestionSqlPair = { qid: number, question: string; sql: string , execution_time: number};

interface QuestionSqlContextProps {
  questionSqlPairs: QuestionSqlPair[];
  setQuestionSqlPairs: React.Dispatch<React.SetStateAction<QuestionSqlPair[]>>;
}

const QuestionSqlContext = createContext<QuestionSqlContextProps | undefined>(undefined);

export const QuestionSqlProvider = ({ children }: { children: ReactNode }) => {
  const [questionSqlPairs, setQuestionSqlPairs] = useState<QuestionSqlPair[]>([]);

  return (
    <QuestionSqlContext.Provider value={{ questionSqlPairs, setQuestionSqlPairs }}>
      {children}
    </QuestionSqlContext.Provider>
  );
};

export const useQuestionSqlContext = () => {
  const context = useContext(QuestionSqlContext);
  if (context === undefined) {
    throw new Error('useQuestionSqlContext must be used within a QuestionSqlProvider');
  }
  return context;
};
