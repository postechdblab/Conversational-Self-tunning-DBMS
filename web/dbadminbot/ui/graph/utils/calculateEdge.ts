import { DatabaseConfig } from "@/ui/graph/types/databaseConfig";
import { EdgeConfig } from "@/ui/graph/types/edgeConfig";
import { calculateSourcePosition } from "@/ui/graph/utils/calculateSourcePosition";
import { calculateTargetPosition } from "@/ui/graph/utils/calculateTargetPosition";
import { edgeClassName } from "@/ui/graph/utils/edgeClassName";
import { edgeMarkerName } from "@/ui/graph/utils/edgeMarkerName";
import { Edge, Node } from "reactflow";

interface CalculateEdgesOptions {
  nodes: Node[];
  currentDatabase: DatabaseConfig;
}

export const calculateEdges = ({ nodes, currentDatabase }: CalculateEdgesOptions) => {
  const initialEdges: Edge[] = [];

  currentDatabase.edgeConfigs.forEach((edgeConfig: EdgeConfig) => {
    const sourceNode = nodes.find((node: Node) => node.id === edgeConfig.source);
    const targetNode = nodes.find((node: Node) => node.id === edgeConfig.target);

    if(sourceNode && targetNode) {
      const sourcePosition = edgeConfig.sourcePosition || calculateSourcePosition(sourceNode.width as number, sourceNode!.position.x, targetNode.width as number, targetNode!.position.x);
      const targetPosition = edgeConfig.targetPosition || calculateTargetPosition(sourceNode.width as number, sourceNode!.position.x, targetNode.width as number, targetNode!.position.x);

      const sourceHandle = `${edgeConfig.sourceKey}-${sourcePosition}`;
      const targetHandle = `${edgeConfig.targetKey}-${targetPosition}`;

      initialEdges.push({
        id: `${edgeConfig.source}-${edgeConfig.target}`,
        source: edgeConfig.source,
        target: edgeConfig.target,
        sourceHandle,
        targetHandle,
        type: "smoothstep",
        markerEnd: edgeMarkerName(edgeConfig, targetPosition),
        className: edgeClassName(edgeConfig, targetPosition)
      });
    }
  });

  return initialEdges;
};