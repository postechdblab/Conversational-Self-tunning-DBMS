import { ChatContextProvider } from "@/context/chatContext";
import { DatabaseContextProvider } from "@/context/databaseContext";
import { TuningResultProvider } from "@/context/dbtuningContext";
import { KnobsContextProvider } from "@/context/knobsContext";
import { KnobSidebarOpenContextContextProvider } from "@/context/knobSideBarContext";
import { QueryResultContextProvider } from "@/context/queryResultContext";
import { QuestionSqlProvider } from "@/context/questionSqlContext";
import { SchemaModalContextContextProvider } from "@/context/schemaModalContext";
import { SidebarOpenContextContextProvider } from "@/context/sideBarContext";
import { WorkloadContextProvider } from "@/context/workloadModalContext";

export function Providers({ children }: { children: React.ReactNode }) {
    return (
        <ChatContextProvider>
            <QueryResultContextProvider>
                <SidebarOpenContextContextProvider>
                    <KnobSidebarOpenContextContextProvider>
                        <TuningResultProvider>
                            <QuestionSqlProvider>
                                <WorkloadContextProvider>
                                    <SchemaModalContextContextProvider>
                                        <DatabaseContextProvider>
                                            <KnobsContextProvider>
                                                {children}
                                            </KnobsContextProvider>
                                        </DatabaseContextProvider>
                                    </SchemaModalContextContextProvider>
                                </WorkloadContextProvider>
                            </QuestionSqlProvider>
                        </TuningResultProvider>
                    </KnobSidebarOpenContextContextProvider>
                </SidebarOpenContextContextProvider>
            </QueryResultContextProvider>
        </ChatContextProvider>
    );
}
