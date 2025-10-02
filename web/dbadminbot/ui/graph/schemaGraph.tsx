"use client";
import { useCallback, useEffect, useState } from "react";
import ReactFlow, {
  Background,
  ControlButton,
  Controls,
  Node,
  NodeChange,
  OnSelectionChangeParams,
  ReactFlowInstance,
  ReactFlowProvider,
  getConnectedEdges,
  getIncomers,
  getOutgoers,
  useEdgesState,
  useNodesState,
  useStoreApi
} from "reactflow";

import InfoIcon from "@/ui/graph/icon/infoIcon";
import InfoPopup from "@/ui/graph/icon/infoPopup";
import Markers from "@/ui/graph/icon/markers";
import MaximizeIcon from "@/ui/graph/icon/maximizeIcon";
import MinimizeIcon from "@/ui/graph/icon/minimizeIcon";
import { nodeTypes } from "@/ui/graph/node";
import { DatabaseConfig } from "@/ui/graph/types/databaseConfig";
import { EdgeConfig } from "@/ui/graph/types/edgeConfig";
import { calculateEdges } from "@/ui/graph/utils/calculateEdge";
import { calculateSourcePosition } from "@/ui/graph/utils/calculateSourcePosition";
import { calculateTargetPosition } from "@/ui/graph/utils/calculateTargetPosition";
import { edgeClassName } from "@/ui/graph/utils/edgeClassName";
import { edgeMarkerName } from "@/ui/graph/utils/edgeMarkerName";
import { initializeNodes } from "@/ui/graph/utils/initializeNodes";
import { loadDatabases } from "@/ui/graph/utils/loadDatabases";
import { logTablePositions } from "@/ui/graph/utils/logTablePositions";
import { moveSVGInFront } from "@/ui/graph/utils/moveSVGInFront";
import { setEdgeClassName } from "@/ui/graph/utils/setEdgeClassName";
import { setHighlightEdgeClassName } from "@/ui/graph/utils/setHighlightEdgeClassName";

// this is important! You need to import the styles from the lib to make it work
import DatabaseIcon from "@/ui/graph/icon/databaseIcon";
import DatabaseMenuPopup from "@/ui/graph/icon/databaseMenuPopup";

import "@/ui/graph/style/column-name.scss";
import "@/ui/graph/style/flow.css";
import "@/ui/graph/style/handle.css";
import "@/ui/graph/style/has-many-edge.scss";
import "@/ui/graph/style/has-one-edge.scss";
import "@/ui/graph/style/info-popup.scss";
import "@/ui/graph/style/key-icon.css";
import "@/ui/graph/style/react-flow.scss";
import "@/ui/graph/style/table.scss";
import "reactflow/dist/style.css";

interface FlowProps {
  currentDatabase: DatabaseConfig;
}

const Flow: React.FC<FlowProps> = (props: FlowProps) => {
  const currentDatabase = props.currentDatabase;
  const initialNodes = initializeNodes(props.currentDatabase);

  const store = useStoreApi();
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [fullscreenOn, setFullScreen] = useState(false);
  const [infoPopupOn, setInfoPopupOn] = useState(false);
  const [unknownDatasetOn, setUnknownDatasetOn] = useState(false);
  const [databaseMenuPopupOn, setDatabaseMenuPopupOn] = useState(false);
  const [nodeHoverActive, setNodeHoverActive] = useState(true);

  const onInit = (instance: ReactFlowInstance) => {
    const nodes = instance.getNodes();
    const initialEdges = calculateEdges({ nodes, currentDatabase });
    setEdges(() => initialEdges);

    const handleKeyboard = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "p") {
        const nodes = instance.getNodes();

        logTablePositions(nodes);
      }
    }

    document.addEventListener("keydown", handleKeyboard)

    // https://javascriptf1.com/snippet/detect-fullscreen-mode-with-javascript
    window.addEventListener("resize", (event) => {
      setFullScreen(window.innerHeight === window.screen.height);
    });

    document.addEventListener("keydown", (e: KeyboardEvent) => {
      if(e.code === "Escape") {
        setInfoPopupOn(false);
        setUnknownDatasetOn(false);
        setDatabaseMenuPopupOn(false);
      }
    });

    // https://stackoverflow.com/questions/42066421/property-value-does-not-exist-on-type-eventtarget
    document.addEventListener("click", (event: Event) => {
      const popup = document.querySelector(".info-popup");

      if(!popup) {
        return;
      }

      const target = (event.target as HTMLInputElement);

      if (target && target.closest(".into-popup-toggle")) {
        return;
      }

      if (target && !target.closest(".info-popup__inner")) {
        setInfoPopupOn(false);
        setUnknownDatasetOn(false);
        setDatabaseMenuPopupOn(false);
      }
    })

    document.addEventListener("keydown", (e: KeyboardEvent) => {
      if(e.code === "MetaLeft") {
        setNodeHoverActive(false);
      }
    }, false);

    document.addEventListener("keyup", (e: KeyboardEvent) => {
      if(e.code === "MetaLeft") {
        setNodeHoverActive(true);
      }
    }, false);
  };

  // https://github.com/wbkd/react-flow/issues/2580
  const onNodeMouseEnter = useCallback(
    (_: any, node: Node) => {
      if(!nodeHoverActive) {
        return;
      }

      const state = store.getState();
      state.resetSelectedElements();
      state.addSelectedNodes([node.id]);

      const connectedEdges = getConnectedEdges([node], edges);
      setEdges(eds => {
        return eds.map((ed) => {
          if (connectedEdges.find(e => e.id === ed.id)) {
            setHighlightEdgeClassName(ed);
          }

          return ed;
        });
      });
    },
    [edges, nodeHoverActive, setEdges, store]
  );

  const onNodeMouseLeave = useCallback(
    (_: any, node: Node) => {
      if(!nodeHoverActive) {
        return;
      }

      const state = store.getState();
      state.resetSelectedElements();

      setEdges(eds =>
        eds.map(ed => setEdgeClassName(ed))
      );

      // https://stackoverflow.com/questions/2520650/how-do-you-clear-the-focus-in-javascript
      (document.activeElement as HTMLElement).blur();
    },
    [nodeHoverActive, setEdges, store]
  );

  const onSelectionChange = useCallback(
    (params: OnSelectionChangeParams) => {
      const edges = params.edges;
      edges.forEach(ed => {
        const svg = document.querySelector(".react-flow__edges")?.querySelector(`[data-testid="rf__edge-${ed.id}"]`)
        moveSVGInFront(svg)
      })
    },
    []
  );

  const handleNodesChange = useCallback(
    (nodeChanges: NodeChange[]) => {
      nodeChanges.forEach(nodeChange => {
        if(nodeChange.type === "position" && nodeChange.positionAbsolute) { // nodeChange.positionAbsolute contains new position
          const node = nodes.find(node => node.id === nodeChange.id);

          if(!node) {
            return;
          }

          const incomingNodes = getIncomers(node, nodes, edges);
          incomingNodes.forEach(incomingNode => {
            const edge = edges.find(edge => {
              return edge.id === `${incomingNode.id}-${node.id}`;
            });

            const edgeConfig = currentDatabase.edgeConfigs.find((edgeConfig: EdgeConfig) => {
              return edgeConfig.source === incomingNode.id && edgeConfig.target === node.id;
            });

            if(nodeChange.positionAbsolute?.x) {
              setEdges(eds =>
                eds.map(ed => {
                  if(edge && ed.id === edge.id) {
                    const sourcePosition = edgeConfig!.sourcePosition || calculateSourcePosition((incomingNode.width as number), incomingNode.position.x, (node.width as number), nodeChange.positionAbsolute!.x);
                    const targetPosition = edgeConfig!.targetPosition || calculateTargetPosition((incomingNode.width as number), incomingNode.position.x, (node.width as number), nodeChange.positionAbsolute!.x);

                    const sourceHandle = `${edgeConfig!.sourceKey}-${sourcePosition}`;
                    const targetHandle = `${edgeConfig!.targetKey}-${targetPosition}`;

                    ed.sourceHandle = sourceHandle;
                    ed.targetHandle = targetHandle;
                    ed.className = edgeClassName(edgeConfig, targetPosition);
                    ed.markerEnd = edgeMarkerName(edgeConfig, targetPosition);
                  }

                  return ed;
                })
              )
            }
          });

          const outgoingNodes = getOutgoers(node, nodes, edges);
          outgoingNodes.forEach(targetNode => {
            const edge = edges.find(edge => {
              return edge.id === `${node.id}-${targetNode.id}`;
            });

            const edgeConfig = currentDatabase.edgeConfigs.find((edgeConfig: EdgeConfig) => {
              return edgeConfig.source === nodeChange.id && edgeConfig.target === targetNode.id;
            });

            if(nodeChange.positionAbsolute?.x) {
              setEdges(eds =>
                eds.map(ed => {
                  if(edge && ed.id === edge.id) {
                    const sourcePosition = edgeConfig!.sourcePosition || calculateSourcePosition((node.width as number), nodeChange.positionAbsolute!.x, (targetNode.width as number), targetNode.position.x);
                    const targetPosition = edgeConfig!.targetPosition || calculateTargetPosition((node.width as number), nodeChange.positionAbsolute!.x, (targetNode.width as number), targetNode.position.x);

                    const sourceHandle = `${edgeConfig!.sourceKey}-${sourcePosition}`;
                    const targetHandle = `${edgeConfig!.targetKey}-${targetPosition}`;

                    ed.sourceHandle = sourceHandle;
                    ed.targetHandle = targetHandle;
                    ed.className = edgeClassName(edgeConfig, targetPosition);
                    ed.markerEnd = edgeMarkerName(edgeConfig, targetPosition);
                  }

                  return ed;
                })
              )
            }
          });
        }
      });

      onNodesChange(nodeChanges);
    },
    [onNodesChange, setEdges, nodes, edges, currentDatabase]
  )

  const toggleFullScreen = () => {
    if(fullscreenOn) {
      document.exitFullscreen().then(function() {
        setFullScreen(false)
      })
      .catch(function(error) {
        alert("Can't exit fullscreen")
        console.error(error)
      });
    } else {
      var element = document.querySelector("body");

      // make the element go to full-screen mode
      element && element.requestFullscreen()
        .then(function() {
          setFullScreen(true)
        })
        .catch(function(error) {
          alert("Can't turn on fullscreen")
          console.error(error)
        });
    }
  }

  // https://stackoverflow.com/questions/16664584/changing-an-svg-markers-color-css
  return (
    <div className="Flow">
      <Markers />
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        snapToGrid={true}
        fitView
        snapGrid={[16, 16]}
        nodeTypes={nodeTypes}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        onSelectionChange={onSelectionChange}
      >
        <Controls showInteractive={false}>
          <ControlButton onClick={toggleFullScreen}>
            {!fullscreenOn && <MaximizeIcon />}
            {fullscreenOn && <MinimizeIcon />}
          </ControlButton>
          <ControlButton onClick={() => { setInfoPopupOn(!infoPopupOn) }} className="into-popup-toggle">
            <InfoIcon />
          </ControlButton>
          <ControlButton onClick={() => { setDatabaseMenuPopupOn(true) }} className="into-popup-toggle">
            <DatabaseIcon />
          </ControlButton>
        </Controls>
        <Background color="#aaa" gap={16} />
      </ReactFlow>
      {infoPopupOn && <InfoPopup onClose={() => { setInfoPopupOn(false) }} />}
      {unknownDatasetOn && <DatabaseMenuPopup
        headline={"Unknown dataset :warning:"}
        subheadline={"Available datasets :point_down:"}
        onClose={() => { setUnknownDatasetOn(false) }} />}
      {databaseMenuPopupOn && <DatabaseMenuPopup
        headline={"Choose a dataset :point_down:"}
        onClose={() => { setDatabaseMenuPopupOn(false) }} />}
    </div>
  );
}

// https://codesandbox.io/s/elastic-elion-dbqwty?file=/src/App.js
// eslint-disable-next-line import/no-anonymous-default-export
export default function SchemaVisualizer({databaseName}: {databaseName:string}){
  const [currentDatabase, setCurrentDatabase] = useState({
    tables: [],
    edgeConfigs: [],
    schemaColors: {},
    tablePositions: {}
  } as DatabaseConfig)
  const [databasesLoaded, setDatabasesLoaded] = useState(false);

  useEffect(() => {
    loadDatabases().then((data) => {
      if(!databaseName || !(databaseName in data)) {
        return;
      }

      const databaseConfig = data[databaseName as string] as DatabaseConfig;
      setCurrentDatabase(databaseConfig);
      setDatabasesLoaded(true);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <ReactFlowProvider>
      {databasesLoaded && <Flow
        currentDatabase={currentDatabase} />
      }
    </ReactFlowProvider>
  )
};
