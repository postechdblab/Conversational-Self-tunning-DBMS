"use client";
import React from "react";
import { SOLBotMessage } from "@/lib/message/types";

export type chatContext = {
    messages: SOLBotMessage[];
    setMessages: React.Dispatch<React.SetStateAction<SOLBotMessage[]>>;
};

const ChatContext = React.createContext<chatContext>({} as chatContext);

export function ChatContextProvider({ children }: { children: React.ReactNode }) {
    const [messages, setMessages] = React.useState<SOLBotMessage[]>([]);
    return (
        <ChatContext.Provider
            value={{
                messages,
                setMessages,
            }}
        >
            {children}
        </ChatContext.Provider>
    );
}

export function useChatContext() {
    const context = React.useContext(ChatContext);
    if (context === undefined) {
        throw new Error("useChatContext must be used within a ChatContextProvider");
    }
    return context;
}
