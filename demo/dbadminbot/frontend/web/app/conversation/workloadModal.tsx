"use client";
import { useDatabaseContext } from "@/context/databaseContext";
import { useWorkloadContext } from "@/context/workloadModalContext";
import { useQuestionSqlContext } from "@/context/questionSqlContext";
import { Button, Modal, ModalBody, ModalContent, ModalFooter, ModalHeader } from "@nextui-org/react";

export default function WorkloadModal({children}: {children: React.ReactNode}) {
    const { selectedDB } = useDatabaseContext();
    const { isWorkloadOpen, setIsWorkloadOpen } = useWorkloadContext();
    const { questionSqlPairs, setQuestionSqlPairs } = useQuestionSqlContext();
    
    const closeHandler = () => {
        setIsWorkloadOpen(false);
    };

    return (
        <>
            <Modal isOpen={isWorkloadOpen} onClose={closeHandler}>
                <ModalContent className="h-full w-full max-w-none">
                    {(onClose) => (
                        <>
                            <ModalHeader className="flex flex-col gap-1">
                                User Questions and Corresponding SQL Queries
                            </ModalHeader>
                            <ModalBody>
                                {/* Display Table for Question-SQL Pairs */}
                                <div className="question-sql-history">
                                    <h3 className="mt-4 mb-2">User Questions and Corresponding SQL Queries</h3>
                                    <table className="question-sql-table w-full border-collapse border border-gray-300">
                                        <thead>
                                            <tr>
                                                <th className="border border-gray-300 p-2">Question ID</th>
                                                <th className="border border-gray-300 p-2">Natural Language Question</th>
                                                <th className="border border-gray-300 p-2">Translated SQL Query</th>
                                                <th className="border border-gray-300 p-2">Execution Time (ms)</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {questionSqlPairs.length > 0 ? (
                                                questionSqlPairs.map((pair, index) => (
                                                    <tr key={index}>
                                                        <td className="border border-gray-300 p-2">{pair.qid}</td>
                                                        <td className="border border-gray-300 p-2">{pair.question}</td>
                                                        <td className="border border-gray-300 p-2">{pair.sql}</td>
                                                        <td className="border border-gray-300 p-2">{pair.execution_time}</td>
                                                    </tr>
                                                ))
                                            ) : (
                                                <tr>
                                                    <td colSpan={4} className="border border-gray-300 p-2 text-center">
                                                        No history available.
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
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
    );
}
