"use client";
import React from "react";

export type knobSidebarOpenContext = {
    isKnobSidebarOpen: boolean;
    setIsKnobSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
};

const KnobSidebarOpenConext = React.createContext<knobSidebarOpenContext>({} as knobSidebarOpenContext);

export function KnobSidebarOpenContextContextProvider({ children }: { children: React.ReactNode }) {
    const [isKnobSidebarOpen, setIsKnobSidebarOpen] = React.useState<boolean>(false);
    return (
        <KnobSidebarOpenConext.Provider
            value={{
                isKnobSidebarOpen,
                setIsKnobSidebarOpen,
            }}
        >
            {children}
        </KnobSidebarOpenConext.Provider>
    );
}

export function useKnobSidebarOpenContext() {
    const context = React.useContext(KnobSidebarOpenConext);
    if (context === undefined) {
        throw new Error("useKnobSidebarOpenContext must be used within a KnobSidebarOpenContextContextProvider");
    }
    return context;
}