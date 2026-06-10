import pandas as pd
import matplotlib.pyplot as plt
import glob
import os

if __name__ == '__main__':
    output_folders = ["results_2_drl_base_5"]
    for folder in output_folders:
        if not os.path.exists(folder):
            print(f"Folder '{folder}' not found, skipping.")
            continue

        print(folder)
        files = glob.glob(os.path.join(folder, "*"))
        if not files:
            print(f"  No subfolders found in '{folder}', skipping.")
            continue

        print(files)
        rewards = pd.DataFrame()
        rewards_sum = pd.DataFrame()
        for file in files:
            state_data_path = os.path.join(file, "state-data.xlsx")
            if not os.path.exists(state_data_path):
                print(f"  '{state_data_path}' not found, skipping.")
                continue
            try:
                state_data = pd.read_excel(state_data_path, sheet_name='Reward', engine='openpyxl')
            except (KeyError, ValueError) as e:
                print(f"  Error reading '{state_data_path}': {e}")
                continue
            state_data_sum = state_data.groupby('Time')['Value'].sum()
            state_data_sum = state_data_sum.reset_index()
            state_data_sum['folder'] = os.path.basename(file)
            state_data['folder'] = os.path.basename(file)
            rewards = pd.concat([rewards, state_data], axis=0, sort=False)
            rewards_sum = pd.concat([rewards_sum, state_data_sum], axis=0, sort=False)

        if rewards.empty:
            print(f"  No reward data found in '{folder}', skipping.")
            continue

        final_agents = rewards['Agent'].unique()
        folders = rewards['folder'].unique()
        parts = folder.split("_")
        num_timesteps = parts[-1] if parts else folder
        print(num_timesteps)
        output_folder = "output_{}".format(num_timesteps)
        os.makedirs(output_folder, exist_ok=True)

        compare_pairs = [["base_drl", "base"], ["m2_drl", "m2"], ["mn1_drl", "mn1"]]
        for pair in compare_pairs:
            case = pair[0].split("_")[0]
            path_to_folder = os.path.join(output_folder, case)
            os.makedirs(path_to_folder, exist_ok=True)

            pair_reward_drl = rewards.loc[rewards['folder'] == pair[0]].reset_index(drop=True)
            pair_reward_base = rewards.loc[rewards['folder'] == pair[1]].reset_index(drop=True)
            if pair_reward_drl.empty and pair_reward_base.empty:
                continue
            plt.plot(pair_reward_drl['Value'])
            plt.plot(pair_reward_base['Value'])
            plt.title("Final Reward Sum")
            plt.legend(pair)
            plt.savefig(os.path.join(path_to_folder, "reward_sum_plot.png"))
            plt.close()

            for agent in final_agents:
                agent_reward_drl = rewards.loc[
                    (rewards['Agent'] == agent) & (rewards['folder'] == pair[0])].reset_index(drop=True)
                agent_reward_base = rewards.loc[
                    (rewards['Agent'] == agent) & (rewards['folder'] == pair[1])].reset_index(drop=True)
                if agent_reward_drl.empty and agent_reward_base.empty:
                    continue
                plt.plot(agent_reward_drl['Value'])
                plt.plot(agent_reward_base['Value'])
                plt.title("{} Final Reward Values".format(agent))
                plt.legend(pair)
                plt.savefig(os.path.join(path_to_folder, "{}.png".format(agent)))
                plt.close()
