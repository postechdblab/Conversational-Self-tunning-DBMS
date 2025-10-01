
export const RESET_MESSAGE = "SESSION_RESET";

export enum MessageType {
    isUser = "isUser",
    isSQL = "isSQL",
    isResultSummary = "isResultSummary",
    isAnalysis = "isAnalysis",
    isSystemMessage = "isSystemMessage",
}

export type SOLBotMessage = {
    message: string;
    confidence: number;
    intent: string | null;
    type: MessageType
};
