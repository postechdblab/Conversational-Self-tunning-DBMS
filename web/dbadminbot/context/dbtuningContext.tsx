// QuestionSqlContext.tsx
"use client"; // Add this line to make the component a Client Component

import React, { createContext, useContext, useState, ReactNode } from 'react';

type TuningResultPair = { qid: number, question: string; sql: string , execution_time: number, execution_time_after_tuning: number};

interface TuningResultContextProps {
  tuningResultPairs: TuningResultPair[];
  setTuningResultPairs: React.Dispatch<React.SetStateAction<TuningResultPair[]>>;
}

const TuningResultContext = createContext<TuningResultContextProps | undefined>(undefined);

export const TuningResultProvider = ({ children }: { children: ReactNode }) => {
  const [tuningResultPairs, setTuningResultPairs] = useState<TuningResultPair[]>([]);

  return (
    <TuningResultContext.Provider value={{ tuningResultPairs, setTuningResultPairs }}>
      {children}
    </TuningResultContext.Provider>
  );
};

export const useTuningResultContext = () => {
  const context = useContext(TuningResultContext);
  if (context === undefined) {
    throw new Error('useTuningResultContext must be used within a TuningResultProvider');
  }
  return context;
};
