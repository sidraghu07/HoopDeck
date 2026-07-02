import styles from "./loading.module.css";

export default function PlayersLoading() {
  return (
    <div className={styles.wrap}>
      <div className={styles.text}>LOADING PLAYERS</div>
      <div className={styles.bar}>
        <div className={styles.fill} />
      </div>
    </div>
  );
}
