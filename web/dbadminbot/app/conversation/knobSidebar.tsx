"use client";
import { useKnobsContext } from "@/context/knobsContext";
import { useKnobSidebarOpenContext } from "@/context/knobSideBarContext";
import SideBar from "@/ui/sidebar/sidebar";
export default function ConversationalKnobSideBar({ children }: { children: React.ReactNode }) {
    const { isKnobSidebarOpen, setIsKnobSidebarOpen } = useKnobSidebarOpenContext();

    const { knobs } = useKnobsContext();
    return (
        <div className="flex flex-row h-screen">
            <SideBar title={"Knob Information"} isOpen={isKnobSidebarOpen} setIsOpen={setIsKnobSidebarOpen}>
                <div className="overflow-x-auto">
                    <table className="table-auto w-full border-collapse border border-gray-300">
                        <thead>
                            <tr>
                                <th className="border border-gray-300 px-4 py-2">Knob Name</th>
                                <th className="border border-gray-300 px-4 py-2">Default Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {knobs.map(([name, value]) => (
                                <tr key={name}>
                                    <td className="border border-gray-300 px-4 py-2">{name}</td>
                                    <td className="border border-gray-300 px-4 py-2">{value}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </SideBar>
            <div className="flex flex-col w-full">{children}</div>
        </div>
    );
}