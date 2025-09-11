# 高温合金知识图谱Schema (Superalloy Knowledge Graph Schema)

本文档定义了用于构建高温合金知识图谱的节点标签（Node Labels）和关系类型（Relationship Types）。Schema的设计旨在全面地捕捉高温合金领域的知识，包括其成分、性能、工艺、应用和失效机理。

## 节点标签 (Node Labels)

节点是知识图谱中的核心实体。

### 核心材料与成分 (Core Materials & Composition)

* `Alloy`: 代表一种具体的高温合金。
    * *属性示例*: `name: string`, `type: string ('wrought' or 'cast')`, `generation: string ('first', 'second', etc.)`

* `AlloyFamily`: 代表一个合金类别。
    * *属性示例*: `name: string` (例如, '镍基高温合金', '单晶高温合金', '粉末冶金高温合金')

* `Element`: 代表一种化学元素。
    * *属性示例*: `name: string`, `symbol: string`, `atomic_number: integer`, `atomic_weight: float`

* `Phase`: 代表合金中的一个具体物相。
    * *属性示例*: `name: string` (例如, 'γ′相', 'γ′′相', 'σ相'), `crystal_structure: string` (例如, 'L1₂', 'D0₂₂')

* `PhaseFamily`: 代表一个通用的物相类别。
    * *属性示例*: `name: string` (例如, 'TCP相', '碳化物', '有序金属间化合物')

### 性能与测试 (Properties & Testing)

* `Property`: 代表合金的一种性能（可作为父标签）。
    * *属性示例*: `name: string`, `value: string`, `unit: string`

* `MechanicalProperty`: 代表一种机械性能。
    * *属性示例*: `name: string` (例如, '蠕变抗力', '屈服强度', '疲劳寿命', '断裂韧性')

* `PhysicalProperty`: 代表一种物理性能。
    * *属性示例*: `name: string` (例如, '密度', '熔点', '热膨胀系数', '热导率')

* `ChemicalProperty`: 代表一种化学性能。
    * *属性示例*: `name: string` (例如, '抗氧化性', '抗热腐蚀性')

* `TestMethod`: 代表用于表征性能的测试方法。
    * *属性示例*: `name: string` (例如, '拉森-米勒蠕变测试', '低周疲劳测试')

### 工艺与制造 (Processing & Manufacturing)

* `ManufacturingProcess`: 代表制造或处理工艺的通用类别。
    * *属性示例*: `name: string`, `description: string`

* `SolidificationProcess`: 代表凝固工艺。
    * *属性示例*: `name: string` (例如, '定向凝固', '投资铸造')

* `WroughtProcess`: 代表变形加工工艺。
    * *属性示例*: `name: string` (例如, '锻造', '挤压')

* `PowderMetallurgyProcess`: 代表粉末冶金工艺。
    * *属性示例*: `name: string` (例如, '惰性气体雾化', '热等静压')

* `HeatTreatment`: 代表热处理工艺。
    * *属性示例*: `name: string` (例如, '固溶处理', '时效处理')

* `CoatingProcess`: 代表涂层制备工艺。
    * *属性示例*: `name: string` (例如, '电子束物理气相沉积(EB-PVD)', '等离子喷涂', '包埋渗')

### 应用与失效 (Application & Failure)

* `Application`: 代表合金的应用领域或具体部件。
    * *属性示例*: `name: string` (例如, '涡轮叶片', '涡轮盘', '燃烧室')

* `Engine`: 代表发动机的具体型号或类型。
    * *属性示例*: `name: string` (例如, 'Trent 800', 'GE90'), `type: string` ('航空发动机', '工业燃气轮机')

* `Defect`: 代表合金或部件中可能出现的缺陷。
    * *属性示例*: `name: string` (例如, '雀斑', '再结晶', '疲劳裂纹')

* `FailureMode`: 代表失效的机理或现象。
    * *属性示例*: `name: string` (例如, '蠕变断裂', '疲劳失效', '涂层剥落')

* `StrengtheningMechanism`: 代表强化机理。
    * *属性示例*: `name: string` (例如, '固溶强化', '沉淀强化')

* `Coating`: 代表用于保护合金的涂层。
    * *属性示例*: `name: string` (例如, '铂铝涂层', 'MCrAlY'), `type: string` ('扩散涂层', '覆盖涂层')

---

## 关系类型 (Relationship Types)

关系是连接不同节点的边，描述了它们之间的联系。

### 材料-成分-结构 (Material-Composition-Structure)

* **`BELONGS_TO_FAMILY`**: 描述合金所属的家族。
    ```
    (Alloy)-[:BELONGS_TO_FAMILY]->(AlloyFamily)
    ```

* **`CONTAINS_ELEMENT`**: 描述合金包含的化学元素。
    ```
    (Alloy)-[:CONTAINS_ELEMENT]->(Element)
    ```
    * *属性*: `weight_percentage: float`, `atomic_percentage: float`

* **`HAS_PHASE`**: 描述合金中存在的物相。
    ```
    (Alloy)-[:HAS_PHASE]->(Phase)
    ```
    * *属性*: `volume_fraction: float`

* **`BELONGS_TO_FAMILY`**: 描述具体物相所属的类别。
    ```
    (Phase)-[:BELONGS_TO_FAMILY]->(PhaseFamily)
    ```

### 材料-性能 (Material-Property)

* **`HAS_PROPERTY`**: 描述合金具有的某种性能。
    ```
    (Alloy)-[:HAS_PROPERTY]->(MechanicalProperty)
    (Alloy)-[:HAS_PROPERTY]->(PhysicalProperty)
    (Alloy)-[:HAS_PROPERTY]->(ChemicalProperty)
    ```

* **`AFFECTS_PROPERTY`**: 描述某个因素（如元素、物相）对性能的影响。
    ```
    (Element)-[:AFFECTS_PROPERTY]->(Property)
    (Phase)-[:AFFECTS_PROPERTY]->(Property)
    ```
    * *属性*: `effect: string` ('improves', 'degrades'), `description: string`

* **`DEGRADES_PROPERTY`**: 描述缺陷对性能的负面影响。
    ```
    (Defect)-[:DEGRADES_PROPERTY]->(Property)
    ```

* **`MEASURED_BY`**: 描述性能是通过哪种方法测量的。
    ```
    (Property)-[:MEASURED_BY]->(TestMethod)
    ```

### 工艺-材料-性能 (Process-Material-Property)

* **`PROCESSED_BY`**: 描述合金经过的制造工艺。
    ```
    (Alloy)-[:PROCESSED_BY]->(ManufacturingProcess)
    ```

* **`INFLUENCES_PROPERTY`**: 描述工艺对最终性能的影响。
    ```
    (ManufacturingProcess)-[:INFLUENCES_PROPERTY]->(Property)
    ```
    * *属性*: `effect: string` ('improves', 'degrades')

* **`CAN_CAUSE_DEFECT`**: 描述工艺可能导致的缺陷。
    ```
    (ManufacturingProcess)-[:CAN_CAUSE_DEFECT]->(Defect)
    ```

### 应用-失效 (Application-Failure)

* **`MADE_OF`**: 描述应用部件是由哪种合金制成的。
    ```
    (Application)-[:MADE_OF]->(Alloy)
    ```

* **`PART_OF`**: 描述部件所属的更宏观的系统。
    ```
    (Application)-[:PART_OF]->(Engine)
    ```

* **`EXPERIENCES_FAILURE_MODE`**: 描述部件可能经历的失效模式。
    ```
    (Application)-[:EXPERIENCES_FAILURE_MODE]->(FailureMode)
    ```
    
* **`CAUSED_BY`**: 描述失效模式的起因。
    ```
    (FailureMode)-[:CAUSED_BY]->(Defect)
    ```

* **`PREVENTS_FAILURE_MODE`**: 描述涂层防止的失效模式。
    ```
    (Coating)-[:PREVENTS_FAILURE_MODE]->(FailureMode)
    ```

* **`APPLIED_BY`**: 描述涂层的制备工艺。
    ```
    (Coating)-[:APPLIED_BY]->(CoatingProcess)
    ```

### 理论与机理 (Theory & Mechanism)

* **`STRENGTHENED_BY`**: 描述合金的核心强化机理。
    ```
    (Alloy)-[:STRENGTHENED_BY]->(StrengtheningMechanism)
    ```

* **`INVOLVES_PHASE`** / **`INVOLVES_DEFECT`**: 描述强化机理所涉及的物相或缺陷。
    ```
    (StrengtheningMechanism)-[:INVOLVES_PHASE]->(Phase)
    (StrengtheningMechanism)-[:INVOLVES_DEFECT]->(Defect)
    ```