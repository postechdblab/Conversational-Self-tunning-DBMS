import { SOLBotMessage, MessageType } from "@/lib/message/types";
import { MessageModel } from "@chatscope/chat-ui-kit-react";

export function DBAdminBotMessageToMessageModel(message: SOLBotMessage): MessageModel {
    return {
        message: message.message,
        position: "single",
        direction: message.type == MessageType.isUser  ? "outgoing" : "incoming",
        sentTime: message.type == MessageType.isUser ? message.intent : message.type == MessageType.isSQL ? `${message.confidence}%` : null,
    } as MessageModel;
}

export function filterUserMessages(messages: SOLBotMessage[]): SOLBotMessage[] {
    return messages.filter(message => message.type == MessageType.isUser);
}

export function filterMessagesByType(messages: SOLBotMessage[], message_type: MessageType): SOLBotMessage[] {
    return messages.filter(message => message.type == message_type);
}