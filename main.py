import numpy as np
import matplotlib.pyplot as plt
import datetime as date
import copy
from ctypes import *


class DistributionParameters():
    # среднеквадратичное отклонение
    scale = 0
    # средний коэффициент массонакопления
    massAccumulationCoefficient = 0
    # количество рыб
    amountFishes = 0
    # массив значений, которые распределены по Гауссу в заданных параметрах
    _gaussValues = []

    def __init__(self, amountFishes,
                 scale=0.003,
                 massAccumulationCoefficientMin=0.07,
                 massAccumulationCoefficientMax=0.087):
        self.massAccumulationCoefficient = (massAccumulationCoefficientMin +
                                       massAccumulationCoefficientMax) / 2
        self.amountFishes = amountFishes
        self.scale = scale
        self._make_gaussian_distribution()

    def _make_gaussian_distribution(self):
        self._gaussValues = np.random.normal(self.massAccumulationCoefficient,
                                        self.scale,
                                        self.amountFishes)
        self._gaussValues.sort()

    def draw_hist_distribution(self, numberFishInOneColumn):
        plt.hist(self._gaussValues, numberFishInOneColumn)
        plt.show()

    def return_array_distributed_values(self):
        return self._gaussValues


def assemble_array(array, amountItems, index):
    result = (c_float * amountItems)()
    for i in range(amountItems):
        result[i] = array[i][index]
    return result


def calculate_end_date_of_month(startDate):
    '''
    result = startDate
    while ((result.day != startDate.day) or
           (result.month == startDate.month)):
        result += date.timedelta(1)
    '''
    month = startDate.month + 1
    year = startDate.year
    if (year > 2100):
        print('Опять ошибка с датами((((((((((((((((((((((((((((')
    if (month > 12):
        month = 1
        year += 1
    result = date.date(year, month, startDate.day)
    return result


def draw_line(start, end, step, current):
    amount = int((end - start) / step) + 1
    percent = current / amount * 100
    print(int(percent), '%')


class FishArray():
    _amountFishes = 0
    _arrayFishes = list()
    _biomass = c_float()
    # массив покупок мальков
    _arrayFryPurchases = list()
    _feedRatio = 1.5
    _dllBuisnessPlan = 0


    def __init__(self, feedRatio=1.5):
        self._feedRatio = c_float(feedRatio)
        self._biomass = c_float()
        self._amountFishes = 0
        self._arrayFishes = list()
        self._arrayFryPurchases = list()
        self._dllBuisnessPlan = WinDLL('D:/github/business_v1.3/Project1/x64/Debug/dllArrayFish.dll')

    def add_biomass(self, date, amountFishes, averageMass):
        # создаем параметры для нормального распределения коэффициентов массонакопления
        distributionParameters = DistributionParameters(amountFishes)
        arrayCoefficients = distributionParameters.return_array_distributed_values()

        # закидываем информацию о новой биомассе в массив
        for i in range(amountFishes):
            # ноль означает (количество дней в бассике, но это не точно
            # arrayFishes = [[startingMass, massAccumulationCoefficient, currentMass],...]
            self._arrayFishes.append([averageMass, arrayCoefficients[i], averageMass])
            self._arrayFryPurchases.append([date, amountFishes, averageMass])

        # увеличиваем количество рыбы в бассейне
        self._amountFishes += amountFishes
        # так как все в граммах, то делим на 1000, чтобы получить килограммы в биомассе
        self._biomass.value += amountFishes * averageMass / 1000

    def add_other_FishArrays(self, fishArray):
        amountNewFishes = len(fishArray)

        # arrayFishes = [[startingMass, massAccumulationCoefficient, currentMass]
        for i in range(amountNewFishes):
            self._biomass.value = self._biomass.value + fishArray[i][2] / 1000
            self._arrayFishes.append(fishArray[i])
        self._amountFishes += amountNewFishes

    def _sort_fish_array(self):
        self._arrayFishes.sort(key=lambda x: x[2])

    def remove_biomass(self, amountFishToRemove):
        self._sort_fish_array()
        removedFishes = list()
        for i in range(amountFishToRemove):
            fish = self._arrayFishes.pop(self._amountFishes - amountFishToRemove)
            removedFishes.append(fish)
            # уменьшаем биомассу
            self._biomass.value -= fish[2] / 1000
        # уменьшаем количество рыб
        self._amountFishes -= amountFishToRemove
        return removedFishes

    def _calculate_correction_factor(self, numberPassedDays, amountAddaptionDays, minKoef, maxKoef):
        b = minKoef
        k = (maxKoef - minKoef) / amountAddaptionDays
        result = k * numberPassedDays + b
        return result

    def daily_work_with_correction_factor(self, numberPassedDays, amountAddaptionDays, minKoef, maxKoef):
        # рассчет корректировочного коэффициента
        if (numberPassedDays <= amountAddaptionDays):
            correctionFactor = self._calculate_correction_factor(numberPassedDays, amountAddaptionDays,
                                                                 minKoef, maxKoef)
        else:
            correctionFactor = 1.0

        correctionFactor = c_float(correctionFactor)

        # подготовим переменные для использования ctypes
        dailyWorkLib = self._dllBuisnessPlan.daily_work_with_correction_factor

        dailyWorkLib.argtypes = [POINTER(c_float), POINTER(c_float),
                                 c_int, c_float, POINTER(c_float), c_float]
        dailyWorkLib.restype = c_float

        # соберем массивы масс и коэффициентов массонакопления
        arrayMass = assemble_array(self._arrayFishes, self._amountFishes, 2)
        arrayMassAccumulationCoefficient = assemble_array(self._arrayFishes,
                                                          self._amountFishes, 1)

        dailyFeedMass = dailyWorkLib(arrayMass, arrayMassAccumulationCoefficient,
                                     self._amountFishes, self._feedRatio,
                                     byref(self._biomass), correctionFactor)

        for i in range(self._amountFishes):
            self._arrayFishes[i][2] = arrayMass[i]

        return dailyFeedMass

    def do_daily_work_some_days(self, amountDays):
        # подготовим переменные для использования ctypes
        dailyWorkLib = self._dllBuisnessPlan.do_daily_work_some_days

        dailyWorkLib.argtypes = [POINTER(c_float), POINTER(c_float),
                                 c_int, c_float, POINTER(c_float), c_int]
        dailyWorkLib.restype = c_float

        # соберем массивы масс и коэффициентов массонакопления
        arrayMass = assemble_array(self._arrayFishes, self._amountFishes, 2)
        arrayMassAccumulationCoefficient = assemble_array(self._arrayFishes,
                                                          self._amountFishes, 1)

        totalFeedMass = dailyWorkLib(arrayMass, arrayMassAccumulationCoefficient,
                                     self._amountFishes, self._feedRatio,
                                     byref(self._biomass), amountDays)

        for i in range(self._amountFishes):
            self._arrayFishes[i][2] = arrayMass[i]

        return totalFeedMass

    def get_amount_fishes(self):
        return self._amountFishes

    def get_array_fish(self):
        return self._arrayFishes

    def calculate_when_fish_will_be_sold(self, massComercialFish,
                                         singleVolume, fishArray):
        # подготовим переменные для использования ctypes
        calculateLib = self._dllBuisnessPlan.calculate_when_fish_will_be_sold

        calculateLib.argtypes = [POINTER(c_float), POINTER(c_float),
                                 c_int, c_float, POINTER(c_float),
                                 c_float, c_int]
        calculateLib.restype = c_int

        amountFish = len(fishArray)
        biomass = 0
        for i in range(amountFish):
            biomass += fishArray[i][2] / 1000
        biomass = c_float(biomass)

        # соберем массивы масс и коэффициентов массонакопления
        arrayMass = assemble_array(fishArray, amountFish, 2)
        arrayMassAccumulationCoefficient = assemble_array(fishArray,
                                                          amountFish, 1)

        amountDays = calculateLib(arrayMass, arrayMassAccumulationCoefficient,
                                  amountFish, self._feedRatio,
                                  byref(biomass), massComercialFish,
                                  singleVolume)

        for i in range(amountFish):
            fishArray[i][2] = arrayMass[i]

        return amountDays

    def calculate_difference_between_number_growth_days_and_limit_days(self, massComercialFish, singleVolume,
                                                                       maxDensity, square):
        calculateLib = self._dllBuisnessPlan.calculate_how_many_fish_needs

        calculateLib.argtypes = [POINTER(c_float), POINTER(c_float),
                                 POINTER(c_float), c_int, c_float,
                                 POINTER(c_float),  POINTER(c_float),
                                 c_float, c_int, c_float, c_float,
                                 POINTER(c_int)]
        calculateLib.restype = c_int

        # соберем массивы масс и коэффициентов массонакопления
        arrayMass1 = assemble_array(self._arrayFishes, self._amountFishes, 2)
        arrayMass2 = assemble_array(self._arrayFishes, self._amountFishes, 2)
        arrayMassAccumulationCoefficient = assemble_array(self._arrayFishes,
                                                          self._amountFishes, 1)
        resultAmountsDays = (c_int * 2)(0)

        biomass1 = c_float(0.0)
        biomass2 = c_float(0.0)

        for i in range(self._amountFishes):
            biomass1.value += arrayMass1[i] / 1000
            biomass2.value += arrayMass1[i] / 1000

        amountDays = calculateLib(arrayMass1, arrayMass2, arrayMassAccumulationCoefficient,
                                  self._amountFishes, self._feedRatio,
                                  byref(biomass1), byref(biomass2), massComercialFish,
                                  singleVolume, maxDensity, square, resultAmountsDays)

        return [amountDays, resultAmountsDays[0], resultAmountsDays[1]]

    def calculate_average_mass(self):
        self.update_biomass()
        if (self._amountFishes != 0):
            result = self._biomass.value / self._amountFishes * 1000
        else:
            result = 0.0
        return result

    def update_biomass(self):
        result = 0
        for i in range(self._amountFishes):
            result += self._arrayFishes[i][2] / 1000
        self._biomass.value = result

    def get_biomass(self):
        return self._biomass.value

    def get_three_fish(self):
        result = [[self._arrayFishes[0][1], self._arrayFishes[0][2]]]
        middle = int(self._amountFishes / 2)
        result.append([self._arrayFishes[middle][1], self._arrayFishes[middle][2]])
        end = self._amountFishes - 1
        result.append([self._arrayFishes[end][1], self._arrayFishes[end][2]])
        return result


class Pool():
    square = 0
    maxPlantingDensity = 0
    arrayFishes = 0
    # количество мальков в 1 упаковке
    singleVolumeFish = 0
    # цена на мальков
    costFishFry = [[5, 35],
                   [10, 40],
                   [20, 45],
                   [30, 50],
                   [50, 60],
                   [100, 130]]
    # массив, в котором хранится информация о покупке мальков
    arrayFryPurchases = list()
    # массив, в котором хранится информация о продаже рыбы
    arraySoldFish = list()
    # текущая плотность посадки
    currentDensity = 0
    # массив кормежек
    feeding = list()
    # масса товарной рыбы
    massComercialFish = 400
    # цена рыбы
    price = 1000
    # индекс зарыбления
    indexFry = 0
    procentOnDepreciationEquipment = 10
    poolHistory = list()


    def __init__(self, square, singleVolumeFish=100, price=850,
                 massComercialFish=400,
                 maximumPlantingDensity=40):
        self.square = square
        self.massComercialFish = massComercialFish
        self.maxPlantingDensity = maximumPlantingDensity
        self.singleVolumeFish = singleVolumeFish
        self.arrayFishes = FishArray()
        self.feeding = list()
        self.arrayFryPurchases = list()
        self.arraySoldFish = list()
        self.poolHistory = list()
        self.price = price

    def add_new_biomass(self, amountFishes, averageMass, newIndex, date):
        self.indexFry = newIndex
        self.arrayFishes.add_biomass(date, amountFishes, averageMass)
        # сохраним инфо о покупки мальков
        # arrayFryPurchases[i] = [date, amountFries, averageMass, totalPrice]
        totalPrice = 0
        for i in range(1, len(self.costFishFry)):
            if (self.costFishFry[i - 1][0] < averageMass <= self.costFishFry[i][0]):
                totalPrice = amountFishes * self.costFishFry[i][1]
                break
            elif (averageMass > 200):
                totalPrice = amountFishes * averageMass
                break
        self.arrayFryPurchases.append([date, amountFishes, averageMass, totalPrice])
        self.currentDensity = amountFishes * (averageMass / 1000) / self.square

    def daily_growth_with_correction_factor(self, day, saveInfo,
                                            numberPassedDays, amountAddaptionDays, minKoef, maxKoef):
        todayFeedMass = self.arrayFishes.daily_work_with_correction_factor(numberPassedDays, amountAddaptionDays,
                                                                           minKoef, maxKoef)
        # сохраняем массы кормежек
        self.feeding.append([day, todayFeedMass])

        # проверяем, есть ли рыба на продажу, и если есть - продаем
        self.sell_fish(day)
        if (saveInfo):
            # [день, количество рыбы, биомасса, средняя масса, плотность]
            self.poolHistory.append([day, self.arrayFishes.get_amount_fishes(), self.arrayFishes.get_biomass(),
                                     self.arrayFishes.calculate_average_mass(), self.update_density()])

    def sell_fish(self, day):
        amountFishForSale = 0
        for i in range(self.arrayFishes.get_amount_fishes()):
            if (self.arrayFishes.get_array_fish()[i][2] >= self.massComercialFish):
                amountFishForSale += 1

        if ((amountFishForSale >= self.singleVolumeFish) or
                ((amountFishForSale == self.arrayFishes.get_amount_fishes()) and
                 (self.arrayFishes.get_amount_fishes() != 0))):
            previousBiomass = self.arrayFishes.get_biomass()
            soldFish = self.arrayFishes.remove_biomass(amountFishForSale)
            # продаем выросшую рыбу и сохраняем об этом инфу
            soldBiomass = 0
            amountSoldFish = 0
            for i in range(len(soldFish)):
                soldBiomass += soldFish[i][2] / 1000
                amountSoldFish += 1

            revenue = soldBiomass * self.price

            self.arraySoldFish.append([day, amountSoldFish, soldBiomass, revenue])
            # обновим density
            self.currentDensity = self.arrayFishes.get_biomass() / self.square
            '''
            print(day, ' indexFry = ', self.indexFry, ' было ', previousBiomass, ' продано: ', soldBiomass,
                  ' стало ', self.arrayFishes.get_biomass(), ' выручка: ', revenue)
            '''

    def update_density(self):
        self.currentDensity = self.arrayFishes.get_biomass() / self.square
        return self.currentDensity

    def calculate_difference_between_number_growth_days_and_limit_days(self, amountFishForSale):
        testFishArray = copy.deepcopy(self.arrayFishes)
        amountDays = testFishArray.calculate_difference_between_number_growth_days_and_limit_days\
            (self.massComercialFish,
             amountFishForSale,
             self.maxPlantingDensity,
             self.square)
        return amountDays


class Module():
    costCWSD = 3000000
    amountPools = 0
    # температура воды
    temperature = 21
    # арендная плата
    rent = 70000
    # стоимость киловатт в час
    costElectricityPerHour = 3.17
    # мощность узв
    equipmentCapacity = 5.6
    # стоимость корма
    feedPrice = 260
    onePoolSquare = 0
    correctionFactor = 2
    pools = list()
    poolsInfo = list()
    masses = list()


    def __init__(self, poolSquare, masses, amountPools=4, correctionFactor=2, singleVolumeFish=100,
                 fishPrice=850, massComercialFish=400, maximumPlantingDensity=40):
        self.onePoolSquare = poolSquare
        self.amountPools = amountPools
        self.correctionFactor = correctionFactor

        self.pools = list()
        self.poolsInfo = list()
        self.masses = masses

        for i in range(amountPools):
            pool = Pool(poolSquare, singleVolumeFish, fishPrice, massComercialFish, maximumPlantingDensity)
            self.pools.append(pool)

    def add_biomass_in_pool(self, poolNumber, amountFishes, mass, newIndex, date):
        self.pools[poolNumber].add_new_biomass(amountFishes, mass, newIndex, date)

    def move_fish_from_one_pool_to_another(self, onePoolNumber, anotherPoolNumber, amountMovedFish):
        # удалим выросшую рыбу из старого бассейна
        removedFish = self.pools[onePoolNumber].arrayFishes.remove_biomass(amountMovedFish)
        # обновим плотность
        self.pools[onePoolNumber].update_density()
        # добавим удаленную рыбу в другой бассейн
        self.pools[anotherPoolNumber].arrayFishes.add_other_FishArrays(removedFish)
        # обновим плотность в другом бассейне
        self.pools[anotherPoolNumber].update_density()
        # теперь в новом бассейне плавает малек с индексом из предыдущего басса
        self.pools[anotherPoolNumber].indexFry = self.pools[onePoolNumber].indexFry

    def total_daily_work_with_correction_factor(self, day, save_pool_info,
                                                numberPassedDays, amountAddaptionDays, minKoef, maxKoef):
        for i in range(self.amountPools):
            self.pools[i].daily_growth_with_correction_factor(day, save_pool_info,
                                                              numberPassedDays, amountAddaptionDays, minKoef, maxKoef)

    def print_info(self):
        print()
        for i in range(self.amountPools):
            print('№', i, ' бассейн, indexFry = ', self.pools[i].indexFry, ', количество рыбы = ',
                  self.pools[i].arrayFishes.get_amount_fishes(),
                  ', биомасса = ', self.pools[i].arrayFishes.get_biomass(),
                  ', средняя масса = ', self.pools[i].arrayFishes.calculate_average_mass(),
                  ', плотность = ', self.pools[i].update_density())
            if (self.pools[i].arrayFishes.get_amount_fishes() != 0):
                # выпишем данные о первых amoutItemes рыбках
                print(self.pools[i].arrayFishes.get_three_fish())
            else:
                print('Рыбы нет')
        print('_______________________________________________________')

    def find_optimal_fry_mass(self, minMass, maxMass, deltaMass):
        minAverageMass = 10000
        for i in range(self.amountPools):
            averageMassInThisPool = self.pools[i].arrayFishes.calculate_average_mass()
            if ((minAverageMass > averageMassInThisPool) and (averageMassInThisPool > 0)):
                minAverageMass = averageMassInThisPool

        result = (int((minAverageMass - deltaMass) / 10)) * 10
        if (result < minMass):
            result = minMass
        elif(result > maxMass):
            result = maxMass

        return result

    def find_empty_pool_and_add_one_volume(self, volumeFish, newIndex, day, deltaMass, minMass, maxMass):
        emptyPool = 0
        for i in range(self.amountPools):
            if (self.pools[i].arrayFishes.get_amount_fishes() == 0):
                emptyPool = i

        optimalMass = self.find_optimal_fry_mass(minMass, maxMass, deltaMass)
        self.pools[emptyPool].add_new_biomass(volumeFish, optimalMass, newIndex, day)

    def find_empty_pool_and_add_twice_volume(self, volumeFish, newIndex, day, koef, deltaMass, minMass, maxMass):
        emptyPool = 0
        for i in range(self.amountPools):
            if (self.pools[i].arrayFishes.get_amount_fishes() == 0):
                emptyPool = i
                break

        optimalMass = self.find_optimal_fry_mass(minMass, maxMass, deltaMass)
        self.pools[emptyPool].add_new_biomass(int(koef * volumeFish), optimalMass, newIndex, day)

    def find_pool_with_twice_volume_and_move_half_in_empty(self):
        overflowingPool = 0
        emptyPool = 0
        maxAmount = 0
        volumeFish = 0
        for i in range(self.amountPools):
            if (self.pools[i].arrayFishes.get_amount_fishes() > maxAmount):
                overflowingPool = i
                maxAmount = self.pools[i].arrayFishes.get_amount_fishes()

            volumeFish = int(maxAmount / 2)

            if (self.pools[i].arrayFishes.get_amount_fishes() == 0):
                emptyPool = i

        self.move_fish_from_one_pool_to_another(overflowingPool, emptyPool, volumeFish)

    def grow_up_fish_in_one_pool_with_correction_factor(self, startDay, startDateSaving,
                                                        numberPassedDays, amountAddaptionDays, minKoef, maxKoef):
        flag = True
        day = startDay
        currentDateSaving = startDateSaving
        currentNumberPassedDays = numberPassedDays

        while (flag):
            while (currentDateSaving < day):
                currentDateSaving = calculate_end_date_of_month(currentDateSaving)

            if (currentDateSaving == day):
                needSave = True
                currentDateSaving = calculate_end_date_of_month(currentDateSaving)
            else:
                needSave = False

            self.total_daily_work_with_correction_factor(day, needSave,
                                                         currentNumberPassedDays, amountAddaptionDays, minKoef, maxKoef)
            day += date.timedelta(1)
            currentNumberPassedDays += 1
            for i in range(self.amountPools):
                if (self.pools[i].arrayFishes.get_amount_fishes() == 0):
                    flag = False
                    break

        return [day, currentNumberPassedDays]

    def grow_up_fish_in_two_pools_with_correction_factor(self, startDay, startDateSaving,
                                                         numberPassedDays, amountAddaptionDays, minKoef, maxKoef):
        flag = True
        day = startDay
        currentDateSaving = startDateSaving
        currentNumberPassedDays = numberPassedDays

        while(flag):
            while (currentDateSaving < day):
                currentDateSaving = calculate_end_date_of_month(currentDateSaving)

            if (currentDateSaving == day):
                needSave = True
                currentDateSaving = calculate_end_date_of_month(currentDateSaving)
                x = currentDateSaving
                y = day

            else:
                needSave = False

            self.total_daily_work_with_correction_factor(day, needSave,
                                                         currentNumberPassedDays, amountAddaptionDays, minKoef, maxKoef)
            day += date.timedelta(1)
            currentNumberPassedDays += 1

            amountEmptyPools = 0
            for i in range(self.amountPools):
                if (self.pools[i].arrayFishes.get_amount_fishes() == 0):
                    amountEmptyPools += 1

            if (amountEmptyPools >= 2):
                flag = False

        return [day, currentNumberPassedDays]

    def start_script_with_correction_factor(self, reserve, startDate, koef, deltaMass,
                                            minMass, maxMass, mainVolumeFish,
                                            amountAddaptionDays, minKoef, maxKoef):
        mainVolumeFish -= reserve

        for i in range(self.amountPools - 1):
            self.pools[i].add_new_biomass(mainVolumeFish, self.masses[i], i, startDate)
        # в бассейн с самой легкой рыбой отправляем в koef раз больше
        self.pools[self.amountPools - 1].indexFry = self.amountPools - 1
        self.pools[self.amountPools - 1].add_new_biomass(int(koef * mainVolumeFish), self.masses[self.amountPools - 1],
                                                          self.amountPools - 1, startDate)

        day = startDate


        # вырастим рыбу в 0 бассейне
        numberPassedDays = 0
        res = self.grow_up_fish_in_one_pool_with_correction_factor(day, startDate,
                                                                   numberPassedDays, amountAddaptionDays,
                                                                   minKoef, maxKoef)
        day = res[0]
        numberPassedDays = res[1]

        # переместим рыбу из 3 в 0 бассейн
        self.find_pool_with_twice_volume_and_move_half_in_empty()

        # вырастим рыбу в 1 бассейне
        res = self.grow_up_fish_in_one_pool_with_correction_factor(day, startDate,
                                                                   numberPassedDays, amountAddaptionDays,
                                                                   minKoef, maxKoef)
        day = res[0]
        numberPassedDays = res[1]

        currentIndex = 4

        # добавим рыбу 2 * mainValue в 1 бассейн
        self.find_empty_pool_and_add_twice_volume(mainVolumeFish, currentIndex, day, koef, deltaMass, minMass, maxMass)
        currentIndex += 1

        # вырастим рыбу в 2 бассейне
        res = self.grow_up_fish_in_one_pool_with_correction_factor(day, startDate,
                                                                   numberPassedDays, amountAddaptionDays,
                                                                   minKoef, maxKoef)
        day = res[0]
        numberPassedDays = res[1]

        return [mainVolumeFish, day, currentIndex, numberPassedDays]

    def main_script_with_correction_factor(self, mainValue, day, previousIndex, startDateSaving,
                                           koef, deltaMass, minMass, maxMass,
                                           numberPassedDays, amountAddaptionDays, minKoef, maxKoef):
        # переместим из переполненного бассейна в пустой половину
        self.find_pool_with_twice_volume_and_move_half_in_empty()

        # вырастим рыбу в 2 бассейнах
        res = self.grow_up_fish_in_two_pools_with_correction_factor(day, startDateSaving,
                                                                    numberPassedDays, amountAddaptionDays,
                                                                    minKoef, maxKoef)
        day = res[0]
        currentNumberPassedDays = res[1]

        currentIndex = previousIndex
        # добавим mainValue штук рыб в пустой бассейн
        self.find_empty_pool_and_add_one_volume(mainValue, currentIndex, day, deltaMass, minMass, maxMass)
        currentIndex += 1

        # добавим koef * mainValue штук рыб в другой пустой бассейн
        self.find_empty_pool_and_add_twice_volume(mainValue, currentIndex, day, koef, deltaMass, minMass, maxMass)
        currentIndex += 1

        # вырастим рыбу в 2 бассейнах
        res = self.grow_up_fish_in_two_pools_with_correction_factor(day, startDateSaving,
                                                                    currentNumberPassedDays, amountAddaptionDays,
                                                                    minKoef, maxKoef)
        day = res[0]
        currentNumberPassedDays = res[1]

        # переместим из переполненного бассейна в пустой
        self.find_pool_with_twice_volume_and_move_half_in_empty()

        # добавим 2 * mainValue штук рыб в другой пустой бассейн
        self.find_empty_pool_and_add_twice_volume(mainValue, currentIndex, day, koef, deltaMass, minMass, maxMass)
        currentIndex += 1

        # вырастим рыбу в 1 бассейне
        res = self.grow_up_fish_in_one_pool_with_correction_factor(day, startDate,
                                                                   currentNumberPassedDays, amountAddaptionDays,
                                                                   minKoef, maxKoef)
        day = res[0]
        currentNumberPassedDays = res[1]

        return [mainValue, day, currentIndex, currentNumberPassedDays]

    def main_work_with_correction_factor(self, startDate, endDate, reserve, deltaMass,
                                         minMass, maxMass, mainVolumeFish,
                                         amountAddaptionDays, minKoef, maxKoef):
        resultStartScript = self.start_script_with_correction_factor(reserve, startDate, self.correctionFactor,
                                                                     deltaMass, minMass, maxMass, mainVolumeFish,
                                                                     amountAddaptionDays, minKoef, maxKoef)

        # [mainVolumeFish, day, currentIndex, numberPassedDays]
        day = resultStartScript[1]
        resultMainScript = self.main_script_with_correction_factor(resultStartScript[0],
                                                                   resultStartScript[1],
                                                                   resultStartScript[2],
                                                                   startDate, self.correctionFactor,
                                                                   deltaMass, minMass, maxMass,
                                                                   resultStartScript[3], amountAddaptionDays,
                                                                   minKoef, maxKoef)

        numberMainScript = 2
        while (day < endDate):
            numberMainScript += 1
            # [mainValue, day, currentIndex]
            resultMainScript = self.main_script_with_correction_factor(resultMainScript[0],
                                                                       resultMainScript[1],
                                                                       resultMainScript[2],
                                                                       startDate, self.correctionFactor,
                                                                       deltaMass, minMass, maxMass,
                                                                       resultMainScript[3], amountAddaptionDays,
                                                                       minKoef, maxKoef)
            day = resultMainScript[1]


class CWSD():
    # Все, что связано с устройством узв
    amountModules = 0
    amountPools = 0
    modules = list()
    square = 0

    # Все, что связано техническими расходами
    salary = 0
    amountWorkers = 0
    equipmentCapacity = 0.0
    rent = 0
    costElectricity = 0
    costCWSD = 0

    # Все, что связано с биорасходами
    feedPrice = 0

    # Все, что связано с резервами
    depreciationReserve = 0
    expansionReserve = 0
    expensesReserve = 0
    depreciationLimit = 0

    # Все, что связано со стартовым капиталом
    principalDebt = 0
    annualPercentage = 0.0
    amountMonth = 0
    grant = 0

    # Все, что связано с периодом адаптации биофильтра
    amountAdaptionDays = 60
    minCorrectonFactor = 0.5
    maxCorrectionFactor = 1.0

    mainVolumeFish = 0

    # финансовая подушка
    financialCushion = 0

    # массивы с основной информацией
    feedings = list()
    fries = list()
    massFriers = list()
    salaries = list()
    rents = list()
    electricities = list()
    revenues = list()
    resultBusinessPlan = list()
    resultBusinessPlanEveryMonth = list()

    # изменяемые в ходе работы параметры
    haveReservesBeenFilled = False
    monthlyPayment = 0
    howMuchIsMissing = 0

    def __init__(self, masses, mainVolumeFish, amountModules=2, amountPools=4, square=10,
                 correctionFactor=2,feedPrice=260, salary=30000,
                 amountWorkers=2, equipmentCapacity=5.5, costElectricity=3.17, rent=100000,
                 costCWSD=3000000, principalDebt=850000, annualPercentage=15.0, amountMonth=12, grant=5000000,
                 fishPrice=850, massCommercialFish=400, singleVolumeFish=100, maximumPlantingDensity=40,
                 financialCushion=300000, depreciationLimit=2000000, amountAdaptionDays=60,
                 minCorrectonFactor=0.5, maxCorrectionFactor=1.0):
        self.amountModules = amountModules
        self.mainVolumeFish = mainVolumeFish
        self.feedPrice = feedPrice
        self.financialCushion = financialCushion
        self.amountAdaptionDays = amountAdaptionDays
        self.minCorrectonFactor = minCorrectonFactor
        self.maxCorrectionFactor = maxCorrectionFactor
        self.modules = list()
        for i in range(amountModules):
            module = Module(square, masses, amountPools, correctionFactor,
                            singleVolumeFish, fishPrice, massCommercialFish,
                            maximumPlantingDensity)
            self.modules.append(module)

        self.amountPools = amountPools
        self.salary = salary
        self.amountWorkers = amountWorkers
        self.equipmentCapacity = equipmentCapacity
        self.costElectricity = costElectricity
        self.rent = rent
        self.costCWSD = costCWSD
        self.depreciationReserve = 0
        self.expansionReserve = 0
        self.principalDebt = principalDebt
        self.annualPercentage = annualPercentage
        self.amountMonth = amountMonth
        self.grant = grant
        self.depreciationLimit = depreciationLimit

        self.feedings = list()
        self.fries = list()
        self.salaries = list()
        self.rents = list()
        self.electricities = list()
        self.revenues = list()
        self.resultBusinessPlan = list()
        self.resultBusinessPlanEveryMonth = list()

    def _calculate_all_casts_and_profits_for_all_period(self, startDate, endDate):
        for i in range(self.amountModules):
            for j in range(self.amountPools):
                for k in range(len(self.modules[i].pools[j].feeding)):
                    # [day, todayFeedMass]
                    self.feedings.append([self.modules[i].pools[j].feeding[k][0],
                                          self.modules[i].pools[j].feeding[k][1] * self.feedPrice])
                for k in range(len(self.modules[i].pools[j].arrayFryPurchases)):
                    # [date, amountFishes, averageMass, totalPrice]
                    self.fries.append([self.modules[i].pools[j].arrayFryPurchases[k][0],
                                      self.modules[i].pools[j].arrayFryPurchases[k][3]])
                for k in range(len(self.modules[i].pools[j].arraySoldFish)):
                    # [day, amountSoldFish, soldBiomass, revenue]
                    self.revenues.append([self.modules[i].pools[j].arraySoldFish[k][0],
                                          self.modules[i].pools[j].arraySoldFish[k][3]])

        startMonth = startDate
        endMonth = calculate_end_date_of_month(startMonth) - date.timedelta(1)
        while (endMonth <= endDate):
            self.rents.append([endMonth, self.rent])
            self.salaries.append([endMonth, self.amountWorkers * self.salary])
            amountDaysInThisMonth = (endMonth - startMonth).days
            self.electricities.append([endMonth,
                                      amountDaysInThisMonth * 24 * self.equipmentCapacity * self.costElectricity])
            startMonth = endMonth + date.timedelta(1)
            endMonth = calculate_end_date_of_month(startMonth) - date.timedelta(1)

    def work_cwsd_with_correction_factor(self, startDate, endDate, reserve, deltaMass, minMass, maxMass):
        for i in range(self.amountModules):
            self.modules[i].main_work_with_correction_factor(startDate, endDate, reserve, deltaMass,
                                                             minMass, maxMass, self.mainVolumeFish,
                                                             self.amountAdaptionDays, self.minCorrectonFactor,
                                                             self.maxCorrectionFactor)

        self._calculate_all_casts_and_profits_for_all_period(startDate, endDate)

    def _find_events_in_this_period(self, array, startPeriod, endPeriod):
        result = 0
        for i in range(len(array)):
            if (startPeriod <= array[i][0] < endPeriod):
                result += array[i][1]
        return result

    def _find_event_on_this_day(self, array, day):
        result = 0
        for i in range(len(array)):
            if (array[i][0] == day):
                result += array[i][1]
        return result

    def _find_money_in_other_fonds(self, neededMoney, useBothReserves):
        restMoney = neededMoney
        amountFundsFoundOnOtherReserves = 0
        avaliableMoneyInExpansionReserve = 0
        avaliableMoneyInDepreciationReserve = 0

        if (restMoney <= self.expansionReserve):
            avaliableMoneyInExpansionReserve = restMoney
        elif (0 <= self.expansionReserve < restMoney):
            avaliableMoneyInExpansionReserve = self.expansionReserve

        self.expansionReserve -= avaliableMoneyInExpansionReserve
        amountFundsFoundOnOtherReserves += avaliableMoneyInExpansionReserve
        restMoney -= avaliableMoneyInExpansionReserve

        if ((restMoney > 0) and (useBothReserves)):
            if (restMoney <= self.depreciationReserve):
                avaliableMoneyInDepreciationReserve = restMoney
            elif (0 <= self.depreciationReserve < restMoney):
                avaliableMoneyInDepreciationReserve = self.depreciationReserve

        self.depreciationReserve -= avaliableMoneyInDepreciationReserve
        amountFundsFoundOnOtherReserves += avaliableMoneyInDepreciationReserve

        return amountFundsFoundOnOtherReserves

    def _calculate_family_profit(self, minSalary, limitSalary, avaliableMoney):
        restMoney = avaliableMoney
        if (restMoney >= limitSalary):
            familyProfit = limitSalary
            restMoney -= familyProfit
        elif (minSalary <= restMoney <= limitSalary):
            delta = limitSalary - avaliableMoney
            familyProfit = avaliableMoney + self._find_money_in_other_fonds(delta, False)
            restMoney = 0
        else:
            familyProfit = 0

        return [familyProfit, restMoney]

    def _add_money_to_additional_reserves(self, avaliableMoney):
        freeMoney = avaliableMoney

        if (self.depreciationReserve < self.depreciationLimit):
            delta = self.depreciationLimit - self.depreciationReserve
            if(delta > freeMoney / 2):
                self.depreciationReserve += freeMoney / 2
                freeMoney -= freeMoney / 2
            else:
                self.depreciationReserve += delta
                freeMoney -= delta
        else:
            delta = self.depreciationReserve - self.depreciationLimit
            self.depreciationReserve -= delta
            freeMoney += delta
        self.expansionReserve += freeMoney

    def controller_reserves(self, expenses, revenue, maxExpenses, minSalary, limitSalary):
        resultMaxExpenses = maxExpenses
        if (expenses > resultMaxExpenses):
            resultMaxExpenses = expenses

        # В первую очередь смотрим, хватает ли денег на резерве для трат на покрытие нынешних трат.
        # Не учитываем деньги из выручки в этом месяце, т.к. может сложиться ситуация,
        # в которой траты пришлись на начало месяца, а выручка на конец
        if (self.expensesReserve < expenses):
            delta = expenses - self.expensesReserve
            self.expensesReserve += self._find_money_in_other_fonds(delta, True)
            # если после взятия денег с других фондов денег не хватает на траты,
            # то это финиш и нужно что-то менять
            if (self.expensesReserve < expenses):
                self.howMuchIsMissing += expenses - self.expensesReserve

        # все ок, убираем из резерва нынешние траты
        self.expensesReserve -= expenses
        # Доступные средства складываются из резерва на траты и уже выручки.
        # Все средства снимаем с резерва для трат (далее РДТ), чтобы не запутаться.
        avaliableMoney = self.expensesReserve
        self.expensesReserve = 0.0
        avaliableMoney += revenue

        # максимальный объем резерва для трат складывается из максимальных трат за все время +
        # финансовая подушка
        volumeExpensesReserve = resultMaxExpenses + self.financialCushion
        currentFamilySalary = 0

        # если доступных средств хватает на заполнение максимального объема РДТ,
        # то все просто, берем сколько нужно в РДТ, остальное идет на
        # резерв на амортизацию и на расширение (далее РДА и РДР) и зп
        if (avaliableMoney >= volumeExpensesReserve):
            self.expensesReserve = volumeExpensesReserve
            avaliableMoney -= volumeExpensesReserve

            # принцип распределения оставшихся доступных средств следующий:
            # половина идет на зп (но не более limitSalary),
            # другая половина идет в РДА и РДР в равном соотношении
            x = self._calculate_family_profit(minSalary, limitSalary, avaliableMoney)
            currentFamilySalary = x[0]
            avaliableMoney = x[1]

            self._add_money_to_additional_reserves(avaliableMoney)

        # если доступных средств не хватает на покрытие максимального объема,
        # то ищем средства на других резервах
        else:
            delta = volumeExpensesReserve - avaliableMoney
            self.expensesReserve += self._find_money_in_other_fonds(delta, True)
            # Если даже средств не хватило, то все доступные деньги идут в РДТ
            # (также деньги из других фондов). То что РДТ будет не полностью заполнен - не страшно,
            # т.к. в следующем месяце траты могут быть небольшими и резерва хватить
            self.expensesReserve += avaliableMoney

        return [currentFamilySalary, resultMaxExpenses]

    def find_minimal_budget(self):
        # item = [конец этого месяца, средства на резерве для расходов с предыдущего месяца,
        #         #         траты на малька, на корм, на зарплату, на ренту, на электричество, месячная плата по кредиту
        #         #         суммарные расходы, выручка, бюджет, обновленный резерв на траты,
        #         #         обновленный резерв на амортизацию, обновленный резерв на расширение, зарплата семье в этом месяце]
        result = [self.resultBusinessPlan[0][10], self.resultBusinessPlan[0][0]]
        for i in range(len(self.resultBusinessPlan)):
            if (result[0] > self.resultBusinessPlan[i][10]):
                result[0] = self.resultBusinessPlan[i][10]
                result[1] = self.resultBusinessPlan[i][0]
        return result

    def print_info(self, startDate):
        startMonth = startDate

        for i in range(len(self.resultBusinessPlan)):
            item = self.resultBusinessPlan[i]
            # item = [конец этого месяца, средства на резерве для расходов с предыдущего месяца,
            #         траты на малька, на корм, на зарплату, на ренту, на электричество, месячная плата по кредиту
            #         суммарные расходы, выручка, бюджет, обновленный резерв на траты,
            #         обновленный резерв на амортизацию, обновленный резерв на расширение, зарплата семье в этом месяце]
            print('------------------------------------------------------------')
            print(i, ' месяц, с ', startMonth, ' по ', item[0])
            print('На конец текущего месяца ситуация в бассейнах будет следующая:')
            for j in range(self.amountModules):
                for k in range(self.amountPools):
                    # [день, количество рыбы, биомасса, средняя масса, плотность]
                    print(j * self.amountPools + k, ' бассейн, количество мальков: ',
                          self.modules[j].pools[k].poolHistory[i][1], ' биомасса: ',
                          self.modules[j].pools[k].poolHistory[i][2], ' средняя масса: ',
                          self.modules[j].pools[k].poolHistory[i][3], ' плотность посадки: ',
                          self.modules[j].pools[k].poolHistory[i][4])

            print('Резерв на расходы в этом месяце: ', item[1])
            print('Будет затрачено на мальков: ', item[2])
            print('На корм: ', item[3])
            print('На зарплату: ', item[4])
            print('На аренду: ', item[5])
            print('На электричество: ', item[6])
            print('Выплаты за кредит: ', item[7])
            print('Общие расходы: ', item[8])
            print('Выручка составит: ', item[9])
            print('Бюджет в этом месяце: ', item[10])
            print('Резерв на расходы в следующем месяце составит: ', item[11])
            print('Резерв на амортизацию составит: ', item[12])
            print('Резерв расширение производства составит: ', item[13])
            print('Зарплата семье в этом месяце составит: ', item[14])
            print()
            startMonth = item[0]

    def print_info_in_this_month(self, startDate):
        item = None

        for i in range(len(self.resultBusinessPlanEveryMonth)):
            if (self.resultBusinessPlanEveryMonth[i][0] == startDate):
                item = self.resultBusinessPlanEveryMonth[i]

        # item = [0 -конец этого месяца, 1 - средства на резерве для расходов с предыдущего месяца,
        #         2 - траты на малька, 3 - на корм, 4 - на зарплату, 5 - на ренту,
        #         6 - на электричество, 7 - месячная плата по кредиту
        #         8 - суммарные расходы, 9 - выручка, 10 - бюджет, 11 - обновленный резерв на траты,
        #         12 - обновленный резерв на амортизацию, 13 - обновленный резерв на расширение,
        #         14 - зарплата семье в этом месяце]
        print('Резерв на расходы в этом месяце: ', item[1])
        print('Будет затрачено на мальков: ', item[2])
        print('На корм: ', item[3])
        print('На зарплату: ', item[4])
        print('На аренду: ', item[5])
        print('На электричество: ', item[6])
        print('Выплаты за кредит: ', item[7])
        print('Общие расходы: ', item[8])
        print('Выручка составит: ', item[9])
        print('Бюджет в этом месяце: ', item[10])
        print('Резерв на расходы в следующем месяце составит: ', item[11])
        print('Резерв на амортизацию составит: ', item[12])
        print('Резерв расширение производства составит: ', item[13])
        print('Зарплата семье в этом месяце составит: ', item[14])
        print()

    def calculate_monthly_loan_payment(self):
        if ((self.principalDebt != 0) and
                (self.annualPercentage != 0) and
                (self.amountMonth != 0)):
            monthlyPercentage = self.annualPercentage / 12 / 100
            annuityRatio = monthlyPercentage * (1 + monthlyPercentage) ** self.amountMonth
            annuityRatio /= (1 + monthlyPercentage) ** self.amountMonth - 1
            monthlyPayment = self.principalDebt * annuityRatio
            self.monthlyPayment = monthlyPayment
        else:
            self.monthlyPayment = 0

    def calculate_cost_launching_new_cwsd(self, startDate):
        self.calculate_monthly_loan_payment()
        x = self.find_minimal_budget()
        amountMonth = int(((x[1] - startDate).days) / 30)
        rest = x[0]
        result = self.grant + self.principalDebt - self.monthlyPayment * amountMonth - rest
        return result

    def calculate_businessPlan_on_one_month(self, startMonth, minSalary, limitSalary,
                                            payForLoan, maxGeneralExpenses):
        endMonth = calculate_end_date_of_month(startMonth)
        currentMaxGeneralExpenses = maxGeneralExpenses

        item = [endMonth, self.expensesReserve]
        bioCost_fries = self._find_events_in_this_period(self.fries, startMonth, endMonth)
        item.append(bioCost_fries)
        bioCost_feedings = self._find_events_in_this_period(self.feedings, startMonth, endMonth)
        item.append(bioCost_feedings)
        techCost_salaries = self._find_events_in_this_period(self.salaries, startMonth, endMonth)
        item.append(techCost_salaries)
        techCost_rents = self._find_events_in_this_period(self.rents, startMonth, endMonth)
        item.append(techCost_rents)
        techCost_electricities = self._find_events_in_this_period(self.electricities, startMonth, endMonth)
        item.append(techCost_electricities)
        revenue = self._find_events_in_this_period(self.revenues, startMonth, endMonth)

        generalExpenses = 0
        if (payForLoan):
            generalExpenses += self.monthlyPayment
        else:
            self.monthlyPayment = 0

        generalExpenses += bioCost_fries + bioCost_feedings + techCost_salaries \
                           + techCost_rents + techCost_electricities

        x = self.controller_reserves(generalExpenses, revenue, currentMaxGeneralExpenses, minSalary, limitSalary)
        currentFamilySalary = x[0]
        currentMaxGeneralExpenses = x[1]

        currentBudget = self.expensesReserve + self.expansionReserve + \
                        self.depreciationReserve + currentFamilySalary

        item.append(self.monthlyPayment)
        item.append(generalExpenses)
        item.append(revenue)
        item.append(currentBudget)
        item.append(self.expensesReserve)
        item.append(self.depreciationReserve)
        item.append(self.expansionReserve)
        item.append(currentFamilySalary)

        # item = [конец этого месяца, средства на резерве для расходов с предыдущего месяца,
        #         траты на малька, на корм, на зарплату, на ренту, на электричество, месячная плата по кредиту
        #         суммарные расходы, выручка, бюджет, обновленный резерв на траты,
        #         обновленный резерв на амортизацию, обновленный резерв на расширение, зарплата семье в этом месяце]
        self.resultBusinessPlanEveryMonth.append(item)

        return currentMaxGeneralExpenses

    def check_calculate_businessPlan_on_one_month(self, startDate, endDate, minSalary, limitSalary):
        startMonth = startDate
        endMonth = calculate_end_date_of_month(startMonth)
        self.expensesReserve = 0
        self.depreciationReserve = (self.principalDebt + self.grant - self.costCWSD) / 2
        self.expansionReserve = (self.principalDebt + self.grant - self.costCWSD) / 2
        self.calculate_monthly_loan_payment()
        currentMonth = 1
        maxGeneralExpenses = 0

        while (endMonth <= endDate):
            if (currentMonth <= self.amountMonth):
                payForLoan = True
            else:
                payForLoan = False

            maxGeneralExpenses = self.calculate_businessPlan_on_one_month(startMonth, minSalary,
                                                         limitSalary, payForLoan,
                                                         maxGeneralExpenses)
            currentMonth += 1
            startMonth = endMonth
            endMonth = calculate_end_date_of_month(startMonth)

        if (len(self.resultBusinessPlan) != len(self.resultBusinessPlanEveryMonth)):
            print('Не совпадают размеры resultBusinessPlan и resultBusinessPlanEveryMonth')
            print('len(self.resultBusinessPlan) = ', len(self.resultBusinessPlan),
                  ' len(self.resultBusinessPlanEveryMonth) = ', len(self.resultBusinessPlanEveryMonth))
            return -1
        else:
            for i in range(len(self.resultBusinessPlan)):
                if (len(self.resultBusinessPlan[i]) != len(self.resultBusinessPlanEveryMonth[i])):
                    print('Не совпадают размеры элементов resultBusinessPlan и resultBusinessPlanEveryMonth')
                    print('i = ', i)
                    print('len(self.resultBusinessPlan[i] = ', len(self.resultBusinessPlan[i]),
                          ' len(self.resultBusinessPlanEveryMonth) = ', len(self.resultBusinessPlanEveryMonth[i]))
                    return -2
                else:
                    for j in range(len(self.resultBusinessPlan[i])):
                        if (self.resultBusinessPlan[i][j] != self.resultBusinessPlanEveryMonth[i][j]):
                            print('Не совпадают ', j, ' пункт ', i, 'элемента')
                            print('self.resultBusinessPlan[i] = ', self.resultBusinessPlan[i],
                                  ' self.resultBusinessPlanEveryMonth[i] = ',
                                  self.resultBusinessPlanEveryMonth[i])
                            print('self.resultBusinessPlan[i][j] = ', self.resultBusinessPlan[i][j],
                                  ' self.resultBusinessPlanEveryMonth[i][j] = ',
                                  self.resultBusinessPlanEveryMonth[i][j])
                            return -3
        print('resultBusinessPlan и resultBusinessPlanEveryMonth совпадают)))))')
        return 0

    def change_parameters(self, newParameters):
        for i in range(len(newParameters)):
            x = newParameters[i]
            if (x[0] == 0):
                self.square = x[1]
            elif (x[0] == 1):
                self.salary = x[1]
            elif (x[0] == 2):
                self.amountWorkers = x[1]
            elif (x[0] == 3):
                self.equipmentCapacity = x[1]
            elif (x[0] == 4):
                self.rent = x[1]
            elif (x[0] == 5):
                self.costElectricity = x[1]
            elif (x[0] == 6):
                self.costCWSD = x[1]
            elif (x[0] == 7):
                self.feedPrice = x[1]
            elif (x[0] == 8):
                self.depreciationLimit = x[1]
            elif (x[0] == 9):
                self.expansionLimit = x[1]
            elif (x[0] == 10):
                self.principalDebt = x[1]
            elif (x[0] == 11):
                self.annualPercentage = x[1]
            elif (x[0] == 12):
                self.amountMonth = x[1]
            elif (x[0] == 13):
                self.grant = x[1]
            elif (x[0] == 14):
                self.financialCushion = x[1]

    def check_business_plan(self):
        # item = [0 -конец этого месяца, 1 - средства на резерве для расходов с предыдущего месяца,
        #         2 - траты на малька, 3 - на корм, 4 - на зарплату, 5 - на ренту,
        #         6 - на электричество, 7 - месячная плата по кредиту
        #         8 - суммарные расходы, 9 - выручка, 10 - бюджет, 11 - обновленный резерв на траты,
        #         12 - обновленный резерв на амортизацию, 13 - обновленный резерв на расширение,
        #         14 - зарплата семье в этом месяце]
        lenBusinessPlan = len(self.resultBusinessPlanEveryMonth)
        totalExpenses = self.costCWSD
        totalRevenue = self.grant + self.principalDebt
        totalFamilyProfit = 0
        finalExpensesReserve = self.resultBusinessPlanEveryMonth[lenBusinessPlan - 1][11]
        finalDepreciationReserve = self.resultBusinessPlanEveryMonth[lenBusinessPlan - 1][12]
        finalExpansionReserve = self.resultBusinessPlanEveryMonth[lenBusinessPlan - 1][13]
        for i in range(len(self.resultBusinessPlanEveryMonth)):
            totalExpenses += self.resultBusinessPlanEveryMonth[i][8]
            totalRevenue += self.resultBusinessPlanEveryMonth[i][9]
            totalFamilyProfit += self.resultBusinessPlanEveryMonth[i][14]

        print('totalExpenses = ', totalExpenses)
        print('totalRevenue = ', totalRevenue)
        print('totalFamilyProfit = ', totalFamilyProfit)
        print('finalExpensesReserve = ', finalExpensesReserve)
        print('finalDepreciationReserve = ', finalDepreciationReserve)
        print('finalExpansionReserve = ', finalExpansionReserve)
        print('totalRevenue - totalExpenses - totalFamilyProfit - finalExpensesReserve - finalDepreciationReserve = ',
              totalRevenue - totalExpenses - totalFamilyProfit - finalExpensesReserve - finalDepreciationReserve)
        if (int(totalRevenue - totalExpenses - totalFamilyProfit -
                finalExpensesReserve - finalDepreciationReserve) == int(finalExpansionReserve)):
            print('Дебет с кребитом сошлись)')


class Business():
    amount_cwsd = 0
    startMasses = list()
    cwsds = list()

    # все, что связано с налогами
    advansePayment = 0.0
    annualRevenue = 0.0
    taxPercent = 5.0

    totalExpenses = 0
    totalRevenue = 0
    totalExpensesReserve = 0
    totalDepreciationReserve = 0
    totalExpansionReserve = 0
    totalFamilyProfit = 0

    totalBusinessPlan = list()

    def __init__(self, startMasses, mainVolume, taxPercent=5.0):
        self.amount_cwsd = 1
        self.startMasses = startMasses
        first_cwsd = CWSD(startMasses, mainVolume)
        self.cwsds = list()
        self.cwsds.append(first_cwsd)

        self.totalExpenses = first_cwsd.costCWSD
        self.totalRevenue = first_cwsd.grant + first_cwsd.principalDebt
        self.totalExpensesReserve = 0
        first_cwsd.depreciationReserve = (first_cwsd.grant + first_cwsd.principalDebt - first_cwsd.costCWSD) / 2
        first_cwsd.expansionReserve = (first_cwsd.grant + first_cwsd.principalDebt - first_cwsd.costCWSD) / 2
        self.totalDepreciationReserve = 0
        self.totalExpansionReserve = 0
        self.totalFamilyProfit = 0

        self.totalBusinessPlan = list()

        self.advansePayment = 0.0
        self.annualRevenue = 0.0
        self.taxPercent = taxPercent

    def add_new_cwsd(self, mainVolume, parameters):
        new_cwsd = CWSD(self.startMasses, mainVolume)
        new_cwsd.change_parameters(parameters)

        new_cwsd.expensesReserve = 0
        new_cwsd.depreciationReserve = (new_cwsd.grant + new_cwsd.principalDebt - new_cwsd.costCWSD) / 2
        new_cwsd.expansionReserve = (new_cwsd.grant + new_cwsd.principalDebt - new_cwsd.costCWSD) / 2
        self.totalExpenses += new_cwsd.costCWSD

        self.amount_cwsd += 1
        self.cwsds.append(new_cwsd)
        print('Начальный бюджет нового узв: ', new_cwsd.grant)
        print('Кредит нового узв: ', new_cwsd.principalDebt)
        print('Время кредита нового узв: ', new_cwsd.amountMonth)
        print('Процент кредита нового узв: ', new_cwsd.annualPercentage)
        print('РДТ нового узв: ', new_cwsd.expensesReserve)
        print('РДА нового узв: ', new_cwsd.depreciationReserve)
        print('РДР нового узв: ', new_cwsd.expansionReserve)
        print()

    def _find_info_in_this_date(self, array, thisDate):
        result = None

        for i in range(len(array)):
            if (array[i][0] == thisDate):
                result = array[i]
                break

        return result

    def calculate_total_business_plan_without_goal(self, startDate, endDate, startNumberMonth, startMaxGeneralExpenses,
                                                   minSalary, limitSalary):
        startMonth = startDate
        endMonth = calculate_end_date_of_month(startMonth)
        currentNumberMonth = startNumberMonth
        currentMaxGeneralExpenses = startMaxGeneralExpenses


        # check_calculate_businessPlan_on_one_month(self, startDate, endDate, minSalary, limitSalary)
        while (endMonth <= endDate):
            currentExpenses = 0
            currentRevenue = 0
            currentExpensesReserve = 0
            currentDepreciationReserve = 0
            currentExpansionReserve = 0
            currentFamilyProfit = 0

            for i in range(self.amount_cwsd):
                if (currentNumberMonth <= self.cwsds[i].amountMonth):
                    payForLoan = True
                else:
                    payForLoan = False

                currentMaxGeneralExpenses = self.cwsds[i].calculate_businessPlan_on_one_month(startMonth, minSalary,
                                                                              limitSalary, payForLoan,
                                                                              currentMaxGeneralExpenses)

                item = self._find_info_in_this_date(self.cwsds[i].resultBusinessPlanEveryMonth, endMonth)
                # item = [0 -конец этого месяца, 1 - средства на резерве для расходов с предыдущего месяца,
                #         2 - траты на малька, 3 - на корм, 4 - на зарплату, 5 - на ренту,
                #         6 - на электричество, 7 - месячная плата по кредиту
                #         8 - суммарные расходы, 9 - выручка, 10 - бюджет, 11 - обновленный резерв на траты,
                #         12 - обновленный резерв на амортизацию, 13 - обновленный резерв на расширение,
                #         14 - зарплата семье в этом месяце]
                currentExpenses += item[8]
                currentRevenue += item[9]
                currentExpensesReserve += item[11]
                currentDepreciationReserve += item[12]
                currentExpansionReserve += item[13]
                currentFamilyProfit += item[14]

            self.totalExpenses += currentExpenses
            self.totalRevenue += currentRevenue
            self.totalExpensesReserve = currentExpensesReserve
            self.totalDepreciationReserve = currentDepreciationReserve
            self.totalExpansionReserve = currentExpansionReserve
            self.totalFamilyProfit += currentFamilyProfit
            x = self.totalRevenue - self.totalExpenses - self.totalExpensesReserve -\
                self.totalDepreciationReserve - self.totalFamilyProfit

            self.totalBusinessPlan.append([endMonth, currentExpenses, self.totalExpenses,
                                           currentRevenue, self.totalRevenue, self.totalExpensesReserve,
                                           self.totalDepreciationReserve, self.totalExpansionReserve,
                                           currentFamilyProfit, self.totalFamilyProfit])

            currentNumberMonth += 1
            startMonth = endMonth
            endMonth = calculate_end_date_of_month(startMonth)

        return [startMonth, currentNumberMonth, currentMaxGeneralExpenses]

    def update_all_reserves(self):
        self.totalExpansionReserve = 0
        self.totalDepreciationReserve = 0
        self.totalExpensesReserve = 0
        for i in range(self.amount_cwsd):
            self.totalExpansionReserve += self.cwsds[i].expansionReserve
            self.totalDepreciationReserve += self.cwsds[i].depreciationReserve
            self.totalExpensesReserve += self.cwsds[i].expensesReserve

    def calculate_total_business_plan_with_goal(self, startDate, endDate,
                                                startNumberMonth, startMaxGeneralExpenses, goalExpansion,
                                                minSalary, limitSalary):
        startMonth = startDate
        endMonth = calculate_end_date_of_month(startMonth)
        currentNumberMonth = startNumberMonth
        currentMaxGeneralExpenses = startMaxGeneralExpenses

        # check_calculate_businessPlan_on_one_month(self, startDate, endDate, minSalary, limitSalary)
        while ((endMonth <= endDate) and (self.totalExpansionReserve < goalExpansion)):
            currentExpenses = 0
            currentRevenue = 0
            currentExpensesReserve = 0
            currentDepreciationReserve = 0
            currentExpansionReserve = 0
            currentFamilyProfit = 0

            for i in range(self.amount_cwsd):
                if (currentNumberMonth <= self.cwsds[i].amountMonth):
                    payForLoan = True
                else:
                    payForLoan = False

                currentMaxGeneralExpenses = self.cwsds[i].calculate_businessPlan_on_one_month(startMonth, minSalary,
                                                                                              limitSalary, payForLoan,
                                                                                              currentMaxGeneralExpenses)

                item = self._find_info_in_this_date(self.cwsds[i].resultBusinessPlanEveryMonth, endMonth)
                # item = [0 -конец этого месяца, 1 - средства на резерве для расходов с предыдущего месяца,
                #         2 - траты на малька, 3 - на корм, 4 - на зарплату, 5 - на ренту,
                #         6 - на электричество, 7 - месячная плата по кредиту
                #         8 - суммарные расходы, 9 - выручка, 10 - бюджет, 11 - обновленный резерв на траты,
                #         12 - обновленный резерв на амортизацию, 13 - обновленный резерв на расширение,
                #         14 - зарплата семье в этом месяце]
                currentExpenses += item[8]
                currentRevenue += item[9]
                currentExpensesReserve += item[11]
                currentDepreciationReserve += item[12]
                currentExpansionReserve += item[13]
                currentFamilyProfit += item[14]

            self.totalExpenses += currentExpenses
            self.totalRevenue += currentRevenue
            self.totalExpensesReserve = currentExpensesReserve
            self.totalDepreciationReserve = currentDepreciationReserve
            self.totalExpansionReserve = currentExpansionReserve
            self.totalFamilyProfit += currentFamilyProfit
            self.totalBusinessPlan.append([endMonth, currentExpenses, self.totalExpenses,
                                           currentRevenue, self.totalRevenue, self.totalExpensesReserve,
                                           self.totalDepreciationReserve, self.totalExpansionReserve,
                                           currentFamilyProfit, self.totalFamilyProfit])

            currentNumberMonth += 1
            startMonth = endMonth
            endMonth = calculate_end_date_of_month(startMonth)

        if (self.totalExpansionReserve >= goalExpansion):
            hasGoalBeenAchieved = True
        else:
            hasGoalBeenAchieved = False

        return [startMonth, currentNumberMonth, currentMaxGeneralExpenses, hasGoalBeenAchieved]

    def calculate_tax(self, currentMonth):
        # функция будет рассчитывать, какой налог нужно заплатить в этом месяце и
        # возвращать результат
        taxInThisMonth = 0.0
        if (currentMonth % 3 == 0):
            taxInThisMonth = self.annualRevenue * self.taxPercent / 100
            taxInThisMonth -= self.advansePayment
            self.advansePayment += taxInThisMonth

        if (currentMonth % 12 == 0):
            self.annualRevenue = 0.0
            self.advansePayment = 0.0

        return taxInThisMonth

    def _remove_total_amount_from_all_reserves(self, neededMoney, key):
        a = list()
        x = list()
        t = neededMoney
        if (key == 'expansionReserve'):
            for i in range(self.amount_cwsd):
                a.append(self.cwsds[i].expansionReserve)
        elif (key == 'depreciationReserve'):
            for i in range(self.amount_cwsd):
                a.append(self.cwsds[i].depreciationReserve)
        elif (key == 'expensesReserve'):
            for i in range(self.amount_cwsd):
                a.append(self.cwsds[i].expensesReserve)

        sum = 0
        for i in range(self.amount_cwsd):
            sum += a[i]

        for i in range(self.amount_cwsd):
            d = t * a[i] / sum
            x.append(d)

        if (key == 'expansionReserve'):
            for i in range(self.amount_cwsd):
                self.cwsds[i].expansionReserve -= x[i]
        elif (key == 'depreciationReserve'):
            for i in range(self.amount_cwsd):
                self.cwsds[i].depreciationReserve -= x[i]
        elif (key == 'expensesReserve'):
            for i in range(self.amount_cwsd):
                self.cwsds[i].expensesReserve -= x[i]

    def _controller_of_all_reserves_for_tax(self, tax, familyProfitInThisMonth):
        neededMoney = tax
        if (neededMoney > 0):
            self.totalExpenses += neededMoney
            if (self.totalExpansionReserve >= neededMoney):
                self._remove_total_amount_from_all_reserves(neededMoney, 'expansionReserve')
                neededMoney = 0.0
            elif (self.totalExpansionReserve > 0):
                self._remove_total_amount_from_all_reserves(self.totalExpansionReserve, 'expansionReserve')
                neededMoney -= self.totalExpansionReserve

            if (neededMoney > 0):
                if (self.totalDepreciationReserve >= neededMoney):
                    self._remove_total_amount_from_all_reserves(neededMoney, 'depreciationReserve')
                    neededMoney = 0.0
                elif (self.totalDepreciationReserve > 0):
                    self._remove_total_amount_from_all_reserves(self.totalDepreciationReserve, 'depreciationReserve')
                    neededMoney -= self.totalDepreciationReserve

            if (neededMoney > 0):
                if (self.totalExpensesReserve >= neededMoney):
                    self._remove_total_amount_from_all_reserves(neededMoney, 'expensesReserve')
                    neededMoney = 0.0
                elif (self.totalExpensesReserve > 0):
                    self._remove_total_amount_from_all_reserves(self.totalExpensesReserve, 'expensesReserve')
                    neededMoney -= self.totalExpensesReserve

            newFamilyProfitInThisMonth = familyProfitInThisMonth
            if (neededMoney > 0):
                if (newFamilyProfitInThisMonth >= neededMoney):
                    newFamilyProfitInThisMonth -= neededMoney
                    neededMoney = 0.0
                else:
                    newFamilyProfitInThisMonth = 0.0
                    neededMoney -= newFamilyProfitInThisMonth

            self.update_all_reserves()

            if (neededMoney > 0):
                return [False, 0.0]
            else:
                return [True, newFamilyProfitInThisMonth]

    def calculate_total_business_plan_with_goal_with_tax(self, startDate, endDate,
                                                         startNumberMonth, startMaxGeneralExpenses, goalExpansion,
                                                         minSalary, limitSalary):
        startMonth = startDate
        endMonth = calculate_end_date_of_month(startMonth)
        currentNumberMonth = startNumberMonth
        currentMaxGeneralExpenses = startMaxGeneralExpenses

        # check_calculate_businessPlan_on_one_month(self, startDate, endDate, minSalary, limitSalary)
        while ((endMonth <= endDate) and (self.totalExpansionReserve < goalExpansion)):
            currentExpenses = 0
            currentRevenue = 0
            currentExpensesReserve = 0
            currentDepreciationReserve = 0
            currentExpansionReserve = 0
            currentFamilyProfit = 0

            for i in range(self.amount_cwsd):
                if (currentNumberMonth <= self.cwsds[i].amountMonth):
                    payForLoan = True
                else:
                    payForLoan = False

                currentMaxGeneralExpenses = self.cwsds[i].calculate_businessPlan_on_one_month(startMonth, minSalary,
                                                                                              limitSalary, payForLoan,
                                                                                              currentMaxGeneralExpenses)

                item = self._find_info_in_this_date(self.cwsds[i].resultBusinessPlanEveryMonth, endMonth)
                # item = [0 -конец этого месяца, 1 - средства на резерве для расходов с предыдущего месяца,
                #         2 - траты на малька, 3 - на корм, 4 - на зарплату, 5 - на ренту,
                #         6 - на электричество, 7 - месячная плата по кредиту
                #         8 - суммарные расходы, 9 - выручка, 10 - бюджет, 11 - обновленный резерв на траты,
                #         12 - обновленный резерв на амортизацию, 13 - обновленный резерв на расширение,
                #         14 - зарплата семье в этом месяце]
                currentExpenses += item[8]
                currentRevenue += item[9]
                currentExpensesReserve += item[11]
                currentDepreciationReserve += item[12]
                currentExpansionReserve += item[13]
                currentFamilyProfit += item[14]

            self.annualRevenue += currentRevenue
            taxInThisMonth = self.calculate_tax(currentNumberMonth)

            self.totalExpenses += currentExpenses
            self.totalRevenue += currentRevenue
            self.totalExpensesReserve = currentExpensesReserve
            self.totalDepreciationReserve = currentDepreciationReserve
            self.totalExpansionReserve = currentExpansionReserve

            if (taxInThisMonth > 0):
                taxResult = self._controller_of_all_reserves_for_tax(taxInThisMonth, currentFamilyProfit)
                currentExpenses += taxInThisMonth
                if (taxResult[0]):
                    currentFamilyProfit = taxResult[1]
                else:
                    print(endMonth, 'Не хватает на налоги, все плохо')

            self.totalFamilyProfit += currentFamilyProfit
            self.totalBusinessPlan.append([endMonth, currentExpenses, self.totalExpenses,
                                           currentRevenue, self.totalRevenue, self.totalExpensesReserve,
                                           self.totalDepreciationReserve, self.totalExpansionReserve,
                                           currentFamilyProfit, self.totalFamilyProfit, taxInThisMonth])

            currentNumberMonth += 1
            startMonth = endMonth
            endMonth = calculate_end_date_of_month(startMonth)

        if (self.totalExpansionReserve >= goalExpansion):
            hasGoalBeenAchieved = True
        else:
            hasGoalBeenAchieved = False

        return [startMonth, currentNumberMonth, currentMaxGeneralExpenses, hasGoalBeenAchieved]

    def calculate_total_business_plan_without_goal_with_tax(self, startDate, endDate, startNumberMonth,
                                                            startMaxGeneralExpenses, minSalary, limitSalary):
        startMonth = startDate
        endMonth = calculate_end_date_of_month(startMonth)
        currentNumberMonth = startNumberMonth
        currentMaxGeneralExpenses = startMaxGeneralExpenses


        # check_calculate_businessPlan_on_one_month(self, startDate, endDate, minSalary, limitSalary)
        while (endMonth <= endDate):
            currentExpenses = 0
            currentRevenue = 0
            currentExpensesReserve = 0
            currentDepreciationReserve = 0
            currentExpansionReserve = 0
            currentFamilyProfit = 0

            for i in range(self.amount_cwsd):
                if (currentNumberMonth <= self.cwsds[i].amountMonth):
                    payForLoan = True
                else:
                    payForLoan = False

                currentMaxGeneralExpenses = self.cwsds[i].calculate_businessPlan_on_one_month(startMonth, minSalary,
                                                                              limitSalary, payForLoan,
                                                                              currentMaxGeneralExpenses)

                item = self._find_info_in_this_date(self.cwsds[i].resultBusinessPlanEveryMonth, endMonth)
                # item = [0 -конец этого месяца, 1 - средства на резерве для расходов с предыдущего месяца,
                #         2 - траты на малька, 3 - на корм, 4 - на зарплату, 5 - на ренту,
                #         6 - на электричество, 7 - месячная плата по кредиту
                #         8 - суммарные расходы, 9 - выручка, 10 - бюджет, 11 - обновленный резерв на траты,
                #         12 - обновленный резерв на амортизацию, 13 - обновленный резерв на расширение,
                #         14 - зарплата семье в этом месяце]
                currentExpenses += item[8]
                currentRevenue += item[9]
                currentExpensesReserve += item[11]
                currentDepreciationReserve += item[12]
                currentExpansionReserve += item[13]
                currentFamilyProfit += item[14]

            self.annualRevenue += currentRevenue
            taxInThisMonth = self.calculate_tax(currentNumberMonth)

            self.totalExpenses += currentExpenses
            self.totalRevenue += currentRevenue
            self.totalExpensesReserve = currentExpensesReserve
            self.totalDepreciationReserve = currentDepreciationReserve
            self.totalExpansionReserve = currentExpansionReserve

            if (taxInThisMonth > 0):
                taxResult = self._controller_of_all_reserves_for_tax(taxInThisMonth, currentFamilyProfit)
                if (taxResult[0]):
                    currentFamilyProfit = taxResult[1]
                else:
                    print(endMonth, 'Не хватает на налоги, все плохо')

            self.totalFamilyProfit += currentFamilyProfit

            self.totalBusinessPlan.append([endMonth, currentExpenses, self.totalExpenses,
                                           currentRevenue, self.totalRevenue, self.totalExpensesReserve,
                                           self.totalDepreciationReserve, self.totalExpansionReserve,
                                           currentFamilyProfit, self.totalFamilyProfit, taxInThisMonth])

            currentNumberMonth += 1
            startMonth = endMonth
            endMonth = calculate_end_date_of_month(startMonth)

        return [startMonth, currentNumberMonth, currentMaxGeneralExpenses]
    def _script_with_goal_with_tax(self, startDate, endDate, startNumberMonth, startMaxGeneralExpenses,
                         costNewCWSD, expansionCushion, minSalary, limitSalary):
        resultBeforeStartingNew_cwsd = self.calculate_total_business_plan_with_goal_with_tax(startDate,
                                                                                             endDate,
                                                                                             startNumberMonth,
                                                                                             startMaxGeneralExpenses,
                                                                                             costNewCWSD +\
                                                                                             expansionCushion,
                                                                                             minSalary, limitSalary)

        dateBeginingSecondCWSD = resultBeforeStartingNew_cwsd[0]
        monthBeginingSecondCWSD = resultBeforeStartingNew_cwsd[1]
        currentMaxGeneralExpenses = resultBeforeStartingNew_cwsd[2]
        canStartNewCWSD = resultBeforeStartingNew_cwsd[3]

        return [canStartNewCWSD, dateBeginingSecondCWSD, monthBeginingSecondCWSD, currentMaxGeneralExpenses]

    def main_script1_with_correction_factor_and_with_tax(self, startDate, endDate, reserve,
                                                         deltaMass, minMass, maxMass, costNewCWSD,
                                                         expansionCushion, mainVolume, minSalary, limitSalary):
        self.cwsds[0].work_cwsd_with_correction_factor(startDate, endDate, reserve, deltaMass, minMass, maxMass)

        firstResult = self._script_with_goal_with_tax(startDate, endDate, 1, 0,
                                                      costNewCWSD, expansionCushion, minSalary, limitSalary)
        if (firstResult[0]):
            # [canStartNewCWSD, dateBeginingSecondCWSD, monthBeginingSecondCWSD, currentMaxGeneralExpenses]
            print(firstResult[1], ' ', firstResult[2],
                  ' месяц - на РДР накопилось достаточно для запуска нового узв')
            self._controller_reserves_when_add_new_cwsd(costNewCWSD, expansionCushion)
            parametersNew_cwsd = [[10, 0], [11, 0], [12, 0], [13, costNewCWSD]]
            self.add_new_cwsd(mainVolume, parametersNew_cwsd)
            self.cwsds[1].work_cwsd_with_correction_factor(firstResult[1], endDate, reserve,
                                                           deltaMass, minMass, maxMass)

            secondResult = self._script_with_goal_with_tax(firstResult[1], endDate, firstResult[2], firstResult[3],
                                                           costNewCWSD, expansionCushion, minSalary, limitSalary)

            if (secondResult[0]):
                print(secondResult[1], ' ', secondResult[2],
                      ' месяц - на РДР накопилось достаточно для запуска нового узв')
                self._controller_reserves_when_add_new_cwsd(costNewCWSD, expansionCushion)
                parametersNew_cwsd = [[10, 0], [11, 0], [12, 0], [13, costNewCWSD]]
                self.add_new_cwsd(mainVolume, parametersNew_cwsd)
                self.cwsds[2].work_cwsd_with_correction_factor(secondResult[1], endDate, reserve,
                                                               deltaMass, minMass, maxMass)
                self.calculate_total_business_plan_without_goal_with_tax(secondResult[1], endDate, secondResult[2],
                                                                         secondResult[3], minSalary, limitSalary)
            else:
                print('Третье узв поставить не успели')
        else:
            print('Второе узв поставить не успели')

    def _controller_reserves_when_add_new_cwsd(self, costNewCWSD, expansionCushion):
        reserves = list()

        sum = 0
        for i in range(self.amount_cwsd):
            reserves.append(self.cwsds[i].expansionReserve - expansionCushion)
            sum += self.cwsds[i].expansionReserve - expansionCushion

        for i in range(self.amount_cwsd):
            x = costNewCWSD * reserves[i] / sum
            self.cwsds[i].expansionReserve -= x
            self.totalExpansionReserve -= x

    def _script_with_goal(self, startDate, endDate, startNumberMonth, startMaxGeneralExpenses,
                         costNewCWSD, expansionCushion, minSalary, limitSalary):
        resultBeforeStartingNew_cwsd = self.calculate_total_business_plan_with_goal(startDate,
                                                                                    endDate,
                                                                                    startNumberMonth,
                                                                                    startMaxGeneralExpenses,
                                                                                    costNewCWSD + expansionCushion,
                                                                                    minSalary, limitSalary)

        dateBeginingSecondCWSD = resultBeforeStartingNew_cwsd[0]
        monthBeginingSecondCWSD = resultBeforeStartingNew_cwsd[1]
        currentMaxGeneralExpenses = resultBeforeStartingNew_cwsd[2]
        canStartNewCWSD = resultBeforeStartingNew_cwsd[3]

        return [canStartNewCWSD, dateBeginingSecondCWSD, monthBeginingSecondCWSD, currentMaxGeneralExpenses]

    def main_script1_with_correction_factor(self, startDate, endDate, reserve,
                                           deltaMass, minMass, maxMass, costNewCWSD,
                                           expansionCushion, mainVolume, minSalary, limitSalary):
        self.cwsds[0].work_cwsd_with_correction_factor(startDate, endDate, reserve, deltaMass, minMass, maxMass)

        firstResult = self._script_with_goal(startDate, endDate, 1, 0,
                                             costNewCWSD, expansionCushion, minSalary, limitSalary)
        if (firstResult[0]):
            # [canStartNewCWSD, dateBeginingSecondCWSD, monthBeginingSecondCWSD, currentMaxGeneralExpenses]
            print(firstResult[1], ' ', firstResult[2],
                  ' месяц - на РДР накопилось достаточно для запуска нового узв')
            self._controller_reserves_when_add_new_cwsd(costNewCWSD, expansionCushion)
            parametersNew_cwsd = [[10, 0], [11, 0], [12, 0], [13, costNewCWSD]]
            self.add_new_cwsd(mainVolume, parametersNew_cwsd)
            self.cwsds[1].work_cwsd_with_correction_factor(firstResult[1], endDate, reserve,
                                                           deltaMass, minMass, maxMass)

            secondResult = self._script_with_goal(firstResult[1], endDate, firstResult[2], firstResult[3],
                                                 costNewCWSD, expansionCushion, minSalary, limitSalary)

            if (secondResult[0]):
                print(secondResult[1], ' ', secondResult[2],
                      ' месяц - на РДР накопилось достаточно для запуска нового узв')
                self._controller_reserves_when_add_new_cwsd(costNewCWSD, expansionCushion)
                parametersNew_cwsd = [[10, 0], [11, 0], [12, 0], [13, costNewCWSD]]
                self.add_new_cwsd(mainVolume, parametersNew_cwsd)
                self.cwsds[2].work_cwsd_with_correction_factor(secondResult[1], endDate, reserve,
                                                               deltaMass, minMass, maxMass)
                self.calculate_total_business_plan_without_goal(secondResult[1], endDate, secondResult[2],
                                                                secondResult[3], minSalary, limitSalary)
            else:
                print('Третье узв поставить не успели')
        else:
            print('Второе узв поставить не успели')

    def print_final_info(self):
        '''
            self.totalExpenses += currentExpenses
            self.totalRevenue += currentRevenue
            self.totalExpensesReserve = currentExpensesReserve
            self.totalDepreciationReserve = currentDepreciationReserve
            self.totalExpansionReserve = currentExpansionReserve
            self.totalFamilyProfit += currentFamilyProfit
        '''
        print()
        print('_________________________________________________________')
        print()
        print('totalExpenses = ', self.totalExpenses)
        print('totalRevenue = ', self.totalRevenue)
        print('totalExpensesReserve = ', self.totalExpensesReserve)
        print('totalDepreciationReserve = ', self.totalDepreciationReserve)
        print('totalFamilyProfit = ', self.totalFamilyProfit)
        print('totalExpansionReserve = ', self.totalExpansionReserve)
        x = self.totalRevenue - self.totalExpenses - self.totalExpensesReserve\
            - self.totalDepreciationReserve - self.totalFamilyProfit
        print('totalRevenue - totalExpenses - totalExpensesReserve - totalDepreciationReserve - totalFamilyProfit = ',
              x)

        if (int(x) == int(self.totalExpansionReserve)):
            print('Глобально тоже все сошлось))))')
        else:
            print('Что-то не сошлось...')

    def print_detailed_info(self):
        for i in range(len(self.totalBusinessPlan)):
            currentEndMonth = self.totalBusinessPlan[i][0]
            currentNumberMonth = i
            amountOperating_cwsd = 0
            for j in range(self.amount_cwsd):
                item = self._find_info_in_this_date(self.cwsds[j].resultBusinessPlanEveryMonth, currentEndMonth)
                if (item != None):
                    amountOperating_cwsd += 1

            print(currentEndMonth, ' ', currentNumberMonth, ' месяц:')
            print('Работает(-ют) ', amountOperating_cwsd, ' узв')
            for j in range(amountOperating_cwsd):
                print(j, ' узв')
                self.cwsds[j].print_info_in_this_month(currentEndMonth)

            # self.totalBusinessPlan.append([0 - endMonth, 1 - currentExpenses, 2 - self.totalExpenses,
            #                                3 - currentRevenue, 4 - self.totalRevenue, 5 - self.totalExpensesReserve,
            #                                6 - self.totalDepreciationReserve, 7 - self.totalExpansionReserve,
            #                                8 - currentFamilyProfit, 9 - self.totalFamilyProfit])
            print('Общий бизнес план:')
            print('Заплаченные налоги в этом месяце: ', self.totalBusinessPlan[i][10])
            print('Расходы в этом месяце = ', self.totalBusinessPlan[i][1])
            print('Расходы за все время до этого месяца = ', self.totalBusinessPlan[i][2])
            print('Доходы в этом месяце = ', self.totalBusinessPlan[i][3])
            print('Доходы за все время до этого месяца = ', self.totalBusinessPlan[i][4])
            print('Общее количество на РДТ = ', self.totalBusinessPlan[i][5])
            print('Общее количество на РДА = ', self.totalBusinessPlan[i][6])
            print('Семейный профит в этом месяце = ', self.totalBusinessPlan[i][8])
            print('Семейный профит за все время до этого месяца = ', self.totalBusinessPlan[i][9])
            print('Общее количество на РДР = ', self.totalBusinessPlan[i][7])

            x = self.totalBusinessPlan[i][4] - self.totalBusinessPlan[i][2] - self.totalBusinessPlan[i][5] \
                - self.totalBusinessPlan[i][6] - self.totalBusinessPlan[i][9]
            print(
                'totalRevenue - totalExpenses - totalExpensesReserve - totalDepreciationReserve - totalFamilyProfit = ',
                x)

            if (int(x) == int(self.totalBusinessPlan[i][7])):
                print('Глобально тоже все сошлось))))')
            else:
                print('Что-то не сошлось...')
            print('==================================================================================================')
            print()

    def result_business(self):
        currentBudget = self.cwsds[0].grant + self.cwsds[0].principalDebt - self.cwsds[0].costCWSD
        result = [True, currentBudget]
        for i in range(len(self.totalBusinessPlan)):
            '''
            self.totalBusinessPlan.append([endMonth, currentExpenses, self.totalExpenses,
                                           currentRevenue, self.totalRevenue, self.totalExpensesReserve,
                                           self.totalDepreciationReserve, self.totalExpansionReserve,
                                           currentFamilyProfit, self.totalFamilyProfit, taxInThisMonth])
            '''
            currentBudget -= self.totalBusinessPlan[i][1]
            if (currentBudget < 0):
                result = [False, 0.0, self.totalBusinessPlan[i][0]]
                break
            else:
                currentBudget += self.totalBusinessPlan[i][3]
                result = [True, currentBudget]

        return result


class NewOptimization():
    def calculate_optimized_amount_fish_in_commercial_pool(self, square, mass,
                                                           startAmount, step, amountTests):
        flagNumber = 0
        amountFish = startAmount
        amountGrowthDays = 0
        amountDaysBeforeLimit = 0
        result = 0

        for i in range(amountTests):
            print(i, ' тест')
            while (flagNumber >= 0):
                pool = Pool(square)
                pool.add_new_biomass(amountFish, mass, 0, date.date.today())
                x = pool.calculate_difference_between_number_growth_days_and_limit_days(amountFish)
                flagNumber = x[0]
                if (flagNumber >= 0):
                    amountFish += step
                    amountGrowthDays = x[1]
                    amountDaysBeforeLimit = x[2]

            result += amountFish

        result /= amountTests
        result = (int(result / 10)) * 10

        return result

    def calculate_cost_launche_new_cwsd(self, amountTests, credit, amountCreditMonth, startMasses, mainVolumeFish,
                                        startDate, endDate, reserve, deltaMass, maxMass):
        averageResult = 0
        minResult = 100000000
        maxResult = 0

        for i in range(amountTests):
            print(i, ' тест')
            newCWSD = CWSD(startMasses, mainVolumeFish)
            '''
            elif (x[0] == 10):
                self.principalDebt = x[1]
            elif (x[0] == 11):
                self.annualPercentage = x[1]
            elif (x[0] == 12):
                self.amountMonth = x[1]
            '''
            changeCreditParameters = [[10, credit], [12, amountCreditMonth]]
            newCWSD.work_cwsd_with_correction_factor(startDate, endDate, reserve, deltaMass, 20, maxMass)
            x = newCWSD.calculate_cost_launching_new_cwsd(startDate)
            averageResult += x
            if (x < minResult):
                minResult = x
            if (x > maxResult):
                maxResult = x
        averageResult /= amountTests

        return [minResult, averageResult, maxResult]


    def total_optimization(self, minCredit, stepCredit, maxCredit, minMaxMass, stepMaxMass, maxMaxMass,
                          minDelta, stepDelta, maxDelta, minAmountMonth, stepAmountMonth, maxAmountMonth,
                          square, mass, startAmount, step, minMass,
                          amountTests, startMasses, reserve, startDate, endDate):
        print('Начат поиск оптимального количества рыбы в коммерческом бассейне')
        amountFishInCommercialPool = self.calculate_optimized_amount_fish_in_commercial_pool(square,
                                                                                             mass, startAmount, step,
                                                                                             amountTests)
        print('В среднем лучше зарыблять ', amountFishInCommercialPool, ' штук в коммерческий бассейн')

        print('Начат поиск оптимальных условий бизнеса')
        maxMinIncome = 0
        bestParameters = [minMaxMass, minDelta, minCredit, minAmountMonth]
        credit = minCredit
        while (credit <= maxCredit):
            amountCreditMonth = minAmountMonth
            while (amountCreditMonth <= maxAmountMonth):
                maxMass = minMaxMass
                while (maxMass <= maxMaxMass):
                    deltaMass = minDelta
                    while (deltaMass <= maxDelta):
                        print('credit = ', credit, ', amountCreditMonth = ', amountCreditMonth,
                              ', maxMass = ', maxMass, ', deltaMass = ', deltaMass)

                        minIncome = 999999999
                        flag = True
                        for i in range(amountTests):
                            print(i, ' тест')
                            newBusiness = Business(startMasses, amountFishInCommercialPool)
                            newBusiness.main_script1_with_correction_factor_and_with_tax(startDate, endDate, reserve,
                                                                                         deltaMass, 20, maxMass,
                                                                                         5000000,
                                                                                         200000,
                                                                                         amountFishInCommercialPool,
                                                                                         100000, 200000)
                            resultBusiness = newBusiness.result_business()

                            if (resultBusiness[0]):
                                if (minIncome > resultBusiness[1]):
                                    minIncome = resultBusiness[1]
                            else:
                                flag = False
                                break

                        if (flag):
                            print('Такие параметры подходят')
                            print('Минимальный доход - траты бизнеса за все время = ',
                                  minIncome)
                            if (maxMinIncome < minIncome):
                                maxMinIncome = minIncome
                                bestParameters = [maxMass, deltaMass, credit, amountCreditMonth]
                        else:
                            print('Такие параметры не подходят, мы можем уйти в минус')
                            print('Ищем другие параметры')
                        print()

                        deltaMass += stepDelta
                    maxMass += stepMaxMass
                amountCreditMonth += stepAmountMonth
            credit += stepCredit

        print('Оптимальные условия:')
        print('credit = ', bestParameters[2], ', amountCreditMonth = ', bestParameters[3],
              ', maxMass = ', bestParameters[0], ', deltaMass = ', bestParameters[1])
        print('Минимальный доход от бизнеса при оптимальных параметрах: ', maxMinIncome)

        return bestParameters


masses = [100, 50, 30, 20]
amountModules = 2
amountPools = 4
poolSquare = 10
# показывает во сколько ра нужно переполнить бассейн
correctionFactor = 2
feedPrice = 260
massCommercialFish = 400
fishPrice = 850
workerSalary = 40000
amountWorkers = 2
cwsdCapacity = 5.5
electricityCost = 3.17
rent = 100000
costCWSD = 3000000
credit = 850000
annualPercentage = 15
amountCreditMonth = 36
grant = 5000000
feedRatio = 1.5

mainVolumeFish = 850

startDate = date.date.today()
endDate = date.date(startDate.year + 5, startDate.month, startDate.day)
reserve = 50
deltaMass = 50
minMass = 20
maxMass = 250
minSalary = 100000
limitSalary = 200000

business = Business(masses, mainVolumeFish)
business.main_script1_with_correction_factor_and_with_tax(startDate, endDate, reserve, deltaMass, minMass,
                                                          maxMass, 4600000, 200000, mainVolumeFish,
                                                          100000, 200000)
business.print_detailed_info()
'''
newOptimization = NewOptimization()
result = newOptimization.total_optimization(500000, 50000, 1000000, 100, 10, 350,
                                            50, 20, 250, 12,
                                            6, 36,
                                            10, 100, 10, 10, 20,
                                            10, masses, reserve, startDate, endDate)
print(result)
'''

