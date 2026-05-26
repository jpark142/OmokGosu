import { Route, Routes } from "react-router-dom";

import Home from "@/routes/Home";
import Game from "@/routes/Game";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/game/:gameId" element={<Game />} />
    </Routes>
  );
}
