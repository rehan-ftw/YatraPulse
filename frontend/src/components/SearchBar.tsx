import { useState } from "react";
import { useNavigate } from "react-router-dom";

export function SearchBar({ initial = "" }: { initial?: string }) {
  const [q, setQ] = useState(initial);
  const navigate = useNavigate();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    navigate(`/search?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <form className="searchbar" onSubmit={submit}>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Enter train number or train name"
        aria-label="Search trains"
      />
      <button className="btn btn-primary btn-lg" type="submit">
        Search train
      </button>
    </form>
  );
}
