import FloatingChatbot from "./FloatingChatbot";
import siteBg from "./assets/images.png";
import "./App.css";

function App() {
  return (
    <div
      className="demo-page"
      style={{ backgroundImage: `url(${siteBg})` }}
      role="img"
      aria-label="Management Concepts website"
    >
      <FloatingChatbot />
    </div>
  );
}

export default App;
