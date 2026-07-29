import FloatingWidgetButton from "./components/FloatingWidgetButton";
import SchdFundPage from "./pages/SchdFundPage";
import { schdFundContentText } from "./data/schdFund";

export default function App() {
  return (
    <>
      <SchdFundPage />
      <FloatingWidgetButton fundContentText={schdFundContentText} />
    </>
  );
}
