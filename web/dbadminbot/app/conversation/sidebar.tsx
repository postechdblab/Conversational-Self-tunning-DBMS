"use client";
import { useDatabaseContext } from "@/context/databaseContext";
import { useSidebarOpenContext } from "@/context/sideBarContext";
import ListBox from "@/ui/listbox/listbox";
import SideBar from "@/ui/sidebar/sidebar";
import { ALL_DB_NAMES } from "@/lib/database/types";

export default function ConversationalSideBar({ children }: { children: React.ReactNode }) {
    const { isSidebarOpen, setIsSidebarOpen } = useSidebarOpenContext();
    const { selectedDB, setSelectedDB } = useDatabaseContext();
    
    return (
        <div className="flex flex-row h-screen">
            <SideBar title={"List of Database"} isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen}>
                <ListBox itemList={ALL_DB_NAMES} selectedItem={selectedDB} setSelectedItem={setSelectedDB} />
            </SideBar>
            <div className="flex flex-col w-full">{children}</div>
        </div>
    );
}
