import { Providers } from "@/app/conversation/providers";
import SchemaViewModal from "@/app/conversation/schemaGraphModal";
import ConversationalSideBar from "@/app/conversation/sidebar";
import ConversationalKnobSideBar from "@/app/conversation/knobSidebar";
import WorkloadModal from "@/app/conversation/workloadModal";

export default function SignUpLayout({ children }: { children: React.ReactNode }) {
    return (
        <Providers>
            <ConversationalSideBar>
                <ConversationalKnobSideBar>
                    <WorkloadModal>
                        <SchemaViewModal>
                            <main className="py-12">
                                {children}
                            </main>
                        </SchemaViewModal>
                    </WorkloadModal>
                </ConversationalKnobSideBar>
            </ConversationalSideBar>
        </Providers>
    );
}
