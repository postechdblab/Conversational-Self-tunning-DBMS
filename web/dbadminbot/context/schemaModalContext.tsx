"use client";
import React from "react";

export type schemaModalContext = {
    isSchemaGraphOpen: boolean;
    setIsSchemaGraphOpen: React.Dispatch<React.SetStateAction<boolean>>;
};

const SchemaModalContext = React.createContext<schemaModalContext>({} as schemaModalContext);

export function SchemaModalContextContextProvider({ children }: { children: React.ReactNode }) {
    const [isSchemaGraphOpen, setIsSchemaGraphOpen] = React.useState<boolean>(false);
    return (
        <SchemaModalContext.Provider
            value={{
                isSchemaGraphOpen,
                setIsSchemaGraphOpen,
            }}
        >
            {children}
        </SchemaModalContext.Provider>
    );
}

export function useSchemaModalContext() {
    const context = React.useContext(SchemaModalContext);
    if (context === undefined) {
        throw new Error("useSchemaModalContext must be used within a SchemaModalContextContextProvider");
    }
    return context;
}
