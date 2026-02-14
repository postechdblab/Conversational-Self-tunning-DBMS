"use client";
import ChatWindow from "@/app/conversation/chatWindow";
import ResultWindow from "@/app/conversation/resultWindow";
import { useKnobsContext } from "@/context/knobsContext";
import { useKnobSidebarOpenContext } from "@/context/knobSideBarContext";
import { useSchemaModalContext } from "@/context/schemaModalContext";
import { useSidebarOpenContext } from "@/context/sideBarContext";
import { useWorkloadContext } from "@/context/workloadModalContext";
import { Button, Divider } from "@nextui-org/react";

export default function Conversation() {
    const { setIsSidebarOpen } = useSidebarOpenContext();
    const { setIsSchemaGraphOpen } = useSchemaModalContext();
    const { setIsKnobSidebarOpen } = useKnobSidebarOpenContext();
    const { setIsWorkloadOpen } = useWorkloadContext();
    const { setKnobs } = useKnobsContext();

    return (
        <div className="">
            <Button className="ml-5" color="primary" variant="flat" onClick={() => setIsSidebarOpen(true)}>
                Select DB
            </Button>
            <Button className="ml-5" color="primary" variant="flat" onClick={() => setIsSchemaGraphOpen(true)}>
                Show schema
            </Button>
            <Button className="ml-5" color="primary" variant="flat" onClick={() => setIsWorkloadOpen(true)}>
                Show Workload
            </Button>
            <Button className="ml-5" color="primary" variant="flat" onClick={async () => {
                setKnobs([]);
                fetch(
                    'http://localhost:1234/knobs',
                    {
                        method: 'POST',
                    },
                ).then(response => response.json()
                ).then(j => setKnobs(j)
                ).catch(err => console.log(err));
                setIsKnobSidebarOpen(true);
            }}>
                Show Knobs
            </Button>
            <div className="p-10 shadow-xl">
                <ResultWindow />
            </div>
            <Divider />
            <div className="shadow-xl my-5">
                <ChatWindow />
            </div>
        </div>
    );
}
