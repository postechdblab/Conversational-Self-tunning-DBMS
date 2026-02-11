"use client";
import React from "react";

export type databaseContext = {
    selectedDB: string;
    setSelectedDB: React.Dispatch<React.SetStateAction<string>>;
};

const DatabaseContext = React.createContext<databaseContext>({} as databaseContext);

export function DatabaseContextProvider({ children }: { children: React.ReactNode }) {
    const [selectedDB, setSelectedDB] = React.useState<string>("");
    return (
        <DatabaseContext.Provider
            value={{
                selectedDB,
                setSelectedDB,
            }}
        >
            {children}
        </DatabaseContext.Provider>
    );
}

export function useDatabaseContext() {
    const context = React.useContext(DatabaseContext);
    if (context === undefined) {
        throw new Error("useDatabaseContext must be used within a DatabaseContextProvider");
    }
    return context;
}
