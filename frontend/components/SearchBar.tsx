import styles from "./SearchBar.module.css";

export default function SearchBar({
  defaultValue = "",
  placeholder = "SEARCH PLAYER NAME...",
}: {
  defaultValue?: string;
  placeholder?: string;
}) {
  return (
    <div className={styles.wrap}>
      <span className={styles.prompt}>&gt;</span>
      <input
        className={styles.input}
        name="name"
        defaultValue={defaultValue}
        placeholder={placeholder}
        spellCheck={false}
        autoComplete="off"
      />
      <button type="submit" className={styles.btn}>SEARCH</button>
    </div>
  );
}
