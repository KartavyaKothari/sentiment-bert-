"""Sentiment analyis

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Zm1so-3JCViti1WO_rsCY7SlF3FPvZlS

# Installing all software
"""

#!pip install torch
#!pip install transformers
#!pip install tqdm

"""# Importing stuff"""

# Commented out IPython magic to ensure Python compatibility.
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import TensorDataset, random_split
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler

import transformers
import nltk
from nltk.corpus import stopwords

from tqdm import tqdm
import re
import datetime
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, accuracy_score, f1_score

import numpy as np
import pandas as pd

# %matplotlib inline
# %pylab inline
# %load_ext autoreload
# %autoreload 2

# if torch.cuda.is_available():    
#     device = torch.device("cuda")

#     print('There are %d GPU(s) available.' % torch.cuda.device_count())
#     print('We will use the GPU:', torch.cuda.get_device_name(0))
# else:
#     print('No GPU available, using the CPU instead.')
#     device = torch.device("cpu")

#!wget -x -c --load-cookies drive/My\ Drive/cookies.txt https://www.kaggle.com/kazanova/sentiment140/download
#!unzip www.kaggle.com/kazanova/sentiment140/download

nltk.download('stopwords')

"""# Data loading and preprocessing class"""

class Data:
  def __init__(self,batchSize,filename):
    self.batchSize = batchSize
    self.dataframe = None
    self.filename = filename
  
  def cleanText(self,text):
    text = re.sub('@\S+|https?:\S+|http?:\S|[^A-Za-z0-9]+',' ',text.lower()).strip()
    
    stop_words = stopwords.words("english")
    tokens = []

    for token in text.split(' '):
      if token not in stop_words:
        tokens.append(token)
    
    return ' '.join(tokens)

  def load_data(self):
    data = pd.read_csv(self.filename,encoding="ISO-8859-1",names = ["target", "ids", "date", "flag", "user", "text"])
    self.dataframe = data[['text','target']].sample(frac=0.1)
    # self.dataframe = self.dataframe.iloc[0:20000]
    print("File read into dataframe")
    return self.preprocess_data()

  def preprocess_data(self):
    # Convert {0,4} to {0,1} labels
    self.dataframe.target = self.dataframe.target.apply(lambda x: x//4)
    print("Converted 04 to 01")

    self.dataframe.text = self.dataframe.text.apply(lambda x: self.cleanText(x))
    print("Cleaned text of stopwords")

    tokenizer = transformers.BertTokenizer.from_pretrained('bert-base-uncased', do_lower_case=True)
    tokenized_text = []
    attention_masks = []

    for q in self.dataframe.text:
      encoded_dict = tokenizer.encode_plus(
                        q,                      # Sentence to encode.
                        add_special_tokens = True, # Add '[CLS]' and '[SEP]'
                        max_length = 50,           # Pad & truncate all sentences.
                        pad_to_max_length = True,
                        truncation = True,
                        return_attention_mask = True,   # Construct attn. masks.
                        return_tensors = 'pt',     # Return pytorch tensors.
                    ) 
      
      tokenized_text.append(encoded_dict['input_ids'])
      attention_masks.append(encoded_dict['attention_mask'])
    print("Bert tokenization complete")

    tokenized_text = torch.cat(tokenized_text, dim=0)
    attention_masks = torch.cat(attention_masks, dim=0)
    labels = torch.tensor([t for t in self.dataframe.target])

    self.tuple_cnt = labels.size()[0]
    dataset = TensorDataset(tokenized_text, attention_masks, labels)
    # print([i for i in dataset],self.tuple_cnt)
    print("Total tuples",len(dataset))
    # dataset = TensorDataset()
    return self.tvt_split(dataset)

  def tvt_split(self,dataset):
    split = [round(i*self.tuple_cnt) for i in [0.5,0.4,0.1]]
    trainSet, testSet, valSet = random_split(dataset, split)

    train_dl = DataLoader(
        trainSet,
        self.batchSize,
        sampler=RandomSampler(trainSet)
    )

    test_dl = DataLoader(
        testSet,
        self.batchSize,
        sampler=SequentialSampler(testSet)
    )

    val_dl = DataLoader(
        valSet,
        self.batchSize,
        sampler=SequentialSampler(valSet)
    )

    return train_dl, test_dl, val_dl

"""# Model"""

class Model(nn.Module):
  def __init__(self,batchSize=32):
    super(Model,self).__init__()
    # Define variables and function modules
    self.batchSize = batchSize
    self.bert=transformers.BertModel.from_pretrained('bert-base-uncased')
    # for p in self.bert.parameters():
    #   p.requires_grad=True
    self.fc = nn.Linear(768,2)
  
  def forward(self,tokenized_text,attention_mask):
    x = self.bert(tokenized_text,attention_mask=attention_mask)[1] #Last hidden state
    # print("&&&",x.size())
    x = self.fc(x.view(self.batchSize,-1))
    x = F.softmax(x, dim=1)
    
    return x

"""# Initiate the training parameters"""

batchSize = 1024
numEpochs = 20
learning_rate = 1e-3

dataset = Data(batchSize,'data/training.1600000.processed.noemoticon.csv')
train_dl, val_dl, test_dl = dataset.load_data()
print("Data preparation complete, training begins now")
model = torch.load('models/sentiment9.pth')
# model.to(device)
# if torch.cuda.is_available():
#   model.cuda()

criteron = nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(),lr=learning_rate)

"""# Train"""

iterations = 0
accuracy_list = []
for epoch in tqdm(range(numEpochs)):
  for ip,mask,label in train_dl:
    model.train()

    if label.shape[0]!=batchSize:
      continue
    output = model(ip,mask)
    optimizer.zero_grad()
    loss = criteron(output,label)
    loss.backward()
    optimizer.step()
  
  model.eval()  
  labels_flat = []
  pred_flat =  []
  valLoss = 0
  for ip,mask,label in val_dl:
    if label.shape[0]!=batchSize:
      continue #Otherwise creates problem with the model architecture

    with torch.no_grad():
      out = model(ip,mask)
    preds = out.detach().numpy()
    pred_flat.extend(np.argmax(preds, axis=1).flatten())
    labels_flat.extend(label.numpy())
    valLoss += criteron(out, label).item()

  print("")
  print("Validation accuracy:", accuracy_score(labels_flat, pred_flat))
  print("Validation F1-micro score:", f1_score(labels_flat, pred_flat, average='micro'))
  print( "Validation Loss:", valLoss)

  torch.save(model,'models/sentiment'+str(epoch)+'.pth')

def TestEvaluation(model, testSet):
  model.eval()
  pred_flat = []
  labels_flat = [] 
  
  for batch in testSet:
    b_input_ids = batch[0]
    b_input_mask = batch[1]
    b_labels = batch[2]
    if b_labels.shape[0]!=batchSize:
      continue

    with torch.no_grad():
      out = model(b_input_ids,b_input_mask)
    preds = out.detach().numpy()
    pred_flat.extend(np.argmax(preds, axis=1).flatten().tolist())
    labels_flat.extend(b_labels.cpu().numpy().flatten().tolist())

  print("Test Accuracy:", accuracy_score(labels_flat, pred_flat))
  print("Test F1-score micro:", f1_score(labels_flat, pred_flat, average='micro'))
# print(classification_report(labels_flat, pred_flat))
print('*'*20)
print("Complete iteration model")
TestEvaluation(model, test_dl)
# print('*'*20)
# print("dataset_file",dataset_file)
# print("type_2_Id_File",type_2_Id_File)
# print("sentence_sequence_length",sentence_sequence_length)
# print("glove_vector_len", glove_vector_len)
# print("input_require_grad",input_require_grad)

# print("input_dim",input_dim)
# print("hidden_dim",hidden_dim)
# print("layer_dim",layer_dim)

# print("batch_size",batch_size)
# print("num_epochs",num_epochs)
# print("learning_rate",learning_rate)
