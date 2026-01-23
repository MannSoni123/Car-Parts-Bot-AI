// import { useEffect, useRef } from 'react';

// export function useSSE(url, onMessage) {
//     const eventSourceRef = useRef(null);

//     useEffect(() => {
//         if (!url) return;

//         const connect = () => {
//             console.log('Connecting to SSE:', url);
//             const eventSource = new EventSource(url);
//             eventSourceRef.current = eventSource;

//             eventSource.onopen = () => {
//                 console.log('SSE connection opened');
//             };

//             eventSource.onmessage = (event) => {
//                 try {
//                     const data = JSON.parse(event.data);
//                     onMessage(data);
//                 } catch (error) {
//                     console.error('Error parsing SSE message:', error);
//                 }
//             };

//             eventSource.onerror = (error) => {
//                 console.error('SSE error:', error);
//                 eventSource.close();

//                 // Retry connection after 5 seconds
//                 setTimeout(() => {
//                     console.log('Retrying SSE connection...');
//                     connect();
//                 }, 5000);
//             };
//         };

//         connect();

//         return () => {
//             if (eventSourceRef.current) {
//                 eventSourceRef.current.close();
//             }
//         };
//     }, [url, onMessage]);
// }
import { useEffect, useRef } from 'react';

export function useSSE(url, onEvent) {
  const sourceRef = useRef(null);

  useEffect(() => {
    if (!url) return;

    const source = new EventSource(url);
    sourceRef.current = source;

    console.log('SSE connected:', url);

    source.onmessage = () => {
      onEvent();
    };

    source.onerror = () => {
      console.error('SSE disconnected, browser will retry...');
      source.close();
    };

    return () => {
      console.log('SSE closed');
      source.close();
    };
  }, [url]); // 🚨 NOT onEvent
}
