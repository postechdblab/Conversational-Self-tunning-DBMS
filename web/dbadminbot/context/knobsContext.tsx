"use client";
import React from "react";

export type KnobsContext = {
    knobs: [string, string][];
    setKnobs: React.Dispatch<React.SetStateAction<[string, string][]>>;
};

const KnobsContext = React.createContext<KnobsContext>({} as KnobsContext);

export function KnobsContextProvider({ children }: { children: React.ReactNode }) {
    const [knobs, setKnobs] = React.useState<[string, string][]>([]);
    return (
        <KnobsContext.Provider
            value={{
                knobs,
                setKnobs,
            }}
        >
            {children}
        </KnobsContext.Provider>
    );
}

export function useKnobsContext() {
    const context = React.useContext(KnobsContext);
    if (context === undefined) {
        throw new Error("useKnobsContext must be used within a KnobsContextProvider");
    }
    return context;
}
