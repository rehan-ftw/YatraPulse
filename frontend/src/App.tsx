import { Route, Routes } from "react-router-dom";
import { LiveProvider } from "./live";
import { AppShell } from "./components/common";
import { Home } from "./pages/Home";
import { SearchResults } from "./pages/SearchResults";
import { TrainDetails } from "./pages/TrainDetails";
import { LiveStatus } from "./pages/LiveStatus";
import { Alerts } from "./pages/Alerts";

export default function App() {
  return (
    <LiveProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<SearchResults />} />
          <Route path="/train/:id" element={<TrainDetails />} />
          <Route path="/live" element={<LiveStatus />} />
          <Route path="/alerts" element={<Alerts />} />
        </Routes>
      </AppShell>
    </LiveProvider>
  );
}
