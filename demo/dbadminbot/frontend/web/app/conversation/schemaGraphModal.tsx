"use client";
import { useDatabaseContext } from "@/context/databaseContext";
import { useSchemaModalContext } from "@/context/schemaModalContext";
import SchemaVisualizer from "@/ui/graph/schemaGraph";
import { Button, Modal, ModalBody, ModalContent, ModalFooter, ModalHeader } from "@nextui-org/react";

const validDBNames = ["concert_singer", "dorm_1", "formula_1", "test_db"]

export default function SchemaViewModal({children}: {children: React.ReactNode}) {
    const { selectedDB } = useDatabaseContext();
    const { isSchemaGraphOpen, setIsSchemaGraphOpen } = useSchemaModalContext();

    const closeHandler = () => {
        setIsSchemaGraphOpen(false);
    }   

    return <>
        <Modal isOpen={isSchemaGraphOpen} onClose={closeHandler}>
            <ModalContent className="h-full w-full max-w-none">
            {(onClose) => (
                <>
                <ModalHeader className="flex flex-col gap-1">Schema of {selectedDB}</ModalHeader>
                <ModalBody>
                   {validDBNames.includes(selectedDB) ?
                   <SchemaVisualizer databaseName={selectedDB}/>
                   :<p>{`Only ${JSON.stringify(validDBNames)} are supported`}</p>
                   }
                </ModalBody>
                <ModalFooter>
                    <Button color="danger" variant="light" onPress={onClose}>
                    Close
                    </Button>
                    <Button color="primary" onPress={onClose}>
                    Ok
                    </Button>
                </ModalFooter>
                </>
            )}
            </ModalContent>
        </Modal>
        {children}
        </>
}