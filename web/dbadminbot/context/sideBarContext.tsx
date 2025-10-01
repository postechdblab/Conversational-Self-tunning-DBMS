"use client";
import React from "react";

export type sidebarOpenContext = {
    isSidebarOpen: boolean;
    setIsSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
};

const SidebarOpenConext = React.createContext<sidebarOpenContext>({} as sidebarOpenContext);

export function SidebarOpenContextContextProvider({ children }: { children: React.ReactNode }) {
    const [isSidebarOpen, setIsSidebarOpen] = React.useState<boolean>(false);
    return (
        <SidebarOpenConext.Provider
            value={{
                isSidebarOpen,
                setIsSidebarOpen,
            }}
        >
            {children}
        </SidebarOpenConext.Provider>
    );
}

export function useSidebarOpenContext() {
    const context = React.useContext(SidebarOpenConext);
    if (context === undefined) {
        throw new Error("useSidebarOpenContext must be used within a SidebarOpenContextContextProvider");
    }
    return context;
}
