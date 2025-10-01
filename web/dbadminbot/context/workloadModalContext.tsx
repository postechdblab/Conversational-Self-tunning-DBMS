"use client";
import React from "react";

export type WorkloadContext = {
    isWorkloadOpen: boolean;
    setIsWorkloadOpen: React.Dispatch<React.SetStateAction<boolean>>;
};

const WorkloadContext = React.createContext<WorkloadContext>({} as WorkloadContext);

export function WorkloadContextProvider({ children }: { children: React.ReactNode }) {
    const [isWorkloadOpen, setIsWorkloadOpen] = React.useState<boolean>(false);
    return (
        <WorkloadContext.Provider
            value={{
                isWorkloadOpen,
                setIsWorkloadOpen,
            }}
        >
            {children}
        </WorkloadContext.Provider>
    );
}

export function useWorkloadContext() {
    const context = React.useContext(WorkloadContext);
    if (context === undefined) {
        throw new Error("useWorkloadContext must be used within a WorkloadContextProvider");
    }
    return context;
}
