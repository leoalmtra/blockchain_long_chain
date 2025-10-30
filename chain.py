import json
import socket
import os
from typing import List
from block import hash_block
from block import Block, create_block, create_block_from_dict, create_genesis_block
from network import broadcast_block, broadcast_transaction, list_peers



def load_chain(fpath: str) -> List[Block]:
    if os.path.exists(fpath):
        with open(fpath) as f:
            data = json.load(f)
            blockchain = []
            for block_data in data:
                block = create_block_from_dict(block_data)
                blockchain.append(block)
            return blockchain

    return [create_genesis_block()]


def save_chain(fpath: str, chain: list[Block]):
    blockchain_serializable = []
    for b in chain:
        blockchain_serializable.append(b.as_dict())

    with open(fpath, "w") as f:
        json.dump(blockchain_serializable, f, indent=2)


def valid_chain(chain: list[Block]) -> bool:
    if chain[0].index != 0 or chain[0].prev_hash != "0" or chain[0].hash != "0":
        print("[!] Invalid Genesis Block.")
        return False

    for i in range(1, len(chain)):
        current_block = chain[i]
        prev_block = chain[i - 1]

        if current_block.index != prev_block.index + 1:
            print(f"[!] Invalid index at block {current_block.index}")
            return False

        if current_block.prev_hash != prev_block.hash:
            print(f"[!] Invalid prev_hash at block {current_block.index}")
            return False

        if current_block.hash != hash_block(current_block):
            print(f"[!] Invalid hash at block {current_block.index}")
            return False

    return True


def print_chain(blockchain: List[Block]):
    for b in blockchain:
        print(f"Index: {b.index}, Hash: {b.hash[:10]}..., Tx: {len(b.transactions)}")


def mine_block(
    transactions: List,
    blockchain: List[Block],
    node_id: str,
    reward: int,
    difficulty: int,
    blockchain_fpath: str,
    peers_fpath: str,
    port: int,
):
    new_block = create_block(
        transactions,
        blockchain[-1].hash,
        miner=node_id,
        index=len(blockchain),
        reward=reward,
        difficulty=difficulty,
    )
    blockchain.append(new_block)
    transactions.clear()
    save_chain(blockchain_fpath, blockchain)
    broadcast_block(new_block, peers_fpath, port)
    print(f"[✓] Block {new_block.index} mined and broadcasted.")


def make_transaction(sender, recipient, amount, transactions, peers_file, port):
    tx = {"from": sender, "to": recipient, "amount": amount}
    transactions.append(tx)
    broadcast_transaction(tx, peers_file, port)
    print("[+] Transaction added.")


def get_balance(node_id: str, blockchain: List[Block]) -> float:
    balance = 0
    for block in blockchain:
        for tx in block.transactions:
            if tx["to"] == node_id:
                balance += float(tx["amount"])
            if tx["from"] == node_id:
                balance -= float(tx["amount"])
    return balance


def on_valid_block_callback(fpath, chain):
    save_chain(fpath, chain)


def resolve_conflicts(
    blockchain: list[Block],
    blockchain_fpath: str,
    peers_fpath: str,
    port: int
) -> bool:

    print("[i] Resolving conflicts...")
    neighbors = list_peers(peers_fpath)
    new_chain = None
    max_len = len(blockchain)

    for peer in neighbors:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer, port))
            s.send(json.dumps({"type": "get_chain"}).encode())
            response_data = s.recv(16384).decode()
            s.close()

            response = json.loads(response_data)
            if response["type"] == "full_chain":
                print("Primeiro if")
                peer_chain_data = response["data"]
                peer_chain_len = len(peer_chain_data)

                if peer_chain_len > max_len-1:
                    print("Segundo if")
                    peer_blockchain = [create_block_from_dict(b) for b in peer_chain_data]

                    if valid_chain(peer_blockchain):
                        print("Terceiro if")
                        max_len = peer_chain_len
                        new_chain = peer_blockchain

        except Exception as e:
            print(f"[!] Could not get chain from peer {peer}: {e}")

    if new_chain:
        blockchain.clear()
        blockchain.extend(new_chain)
        save_chain(blockchain_fpath, blockchain)
        print("[✓] Chain was replaced by a longer valid chain.")
        return True

    print("[i] Our chain is authoritative.")
    return False
